from __future__ import annotations
from builtins import range
import traceback
from io import open
from typing import Union, Any, Dict, List, Set, Tuple, Optional, Callable
from typing_extensions import Literal
from aeel_types import OptionsDictT, WebSocketT
# import gevent as gvt
import json as jsn
# import bottle as btl
try:
    import bottle_websocket as wbs
except ImportError:
    import bottle.ext.websocket as wbs
import re as rgx
import os
import browsers as brw
import pyparsing as pp
import random as rnd
import sys
import importlib_resources
import socket
import mimetypes

from quart import Quart, websocket, Response, send_from_directory
import asyncio
from pprint import pprint
from icecream import ic
ic.configureOutput(prefix='async_eel| ')


class AsyncEel:

    def __init__(self):
        mimetypes.add_type('application/javascript', '.js')

        # https://setuptools.pypa.io/en/latest/pkg_resources.html
        #     Use of pkg_resources is deprecated in favor of importlib.resources
        # Migration guide: https://importlib-resources.readthedocs.io/en/latest/migration.html
        self._eel_js_reference = importlib_resources.files('async_eel') / 'async_eel.js'
        with importlib_resources.as_file(self._eel_js_reference) as _eel_js_path:
            self._eel_js: str = _eel_js_path.read_text(encoding='utf-8')

        self._websockets: List[Tuple[Any, WebSocketT]] = []
        self._call_return_values: Dict[Any, Any] = {}
        self._call_return_callbacks: Dict[float, Tuple[Callable[..., Any], Optional[Callable[..., Any]]]] = {}
        self._call_number: int = 0
        self._exposed_functions: Dict[Any, Any] = {}
        self._js_functions: List[Any] = []
        self._mock_queue: List[Any] = []
        self._mock_queue_done: Set[Any] = set()
        self.app: Quart = Quart(__name__)
        # self._shutdown: Optional[gvt.Greenlet] = None    # Later assigned as global by _websocket_close()
        self.root_path: str                              # Later assigned as global by init()

        # The maximum time (in milliseconds) that Python will try to retrieve a return value for functions executing in JS
        # Can be overridden through `eel.init` with the kwarg `js_result_timeout` (default: 10000)
        self._js_result_timeout: int = 10000

        # Attribute holding the start args from calls to eel.start()
        self._start_args: OptionsDictT = {}

        # == Temporary (suppressible) error message to inform users of breaking API change for v1.0.0 ===
        self.api_error_message: str = '''
        ----------------------------------------------------------------------------------
          'options' argument deprecated in v1.0.0, see https://github.com/ChrisKnott/Eel
          To suppress this error, add 'suppress_error=True' to start() call.
          This option will be removed in future versions
        ----------------------------------------------------------------------------------
        '''

        # PyParsing grammar for parsing exposed functions in JavaScript code
        # Examples: `eel.expose(w, "func_name")`, `eel.expose(func_name)`, `eel.expose((function (e){}), "func_name")`
        self.EXPOSED_JS_FUNCTIONS: pp.ZeroOrMore = pp.ZeroOrMore(
            pp.Suppress(
                pp.SkipTo(pp.Literal('eel.expose('))
                + pp.Literal('eel.expose(')
                + pp.Optional(
                    pp.Or([pp.nestedExpr(), pp.Word(pp.printables, excludeChars=',')]) + pp.Literal(',')
                )
            )
            + pp.Suppress(pp.Regex(r'["\']?'))
            + pp.Word(pp.printables, excludeChars='"\')')
            + pp.Suppress(pp.Regex(r'["\']?\s*\)')),
        )

        self.BOTTLE_ROUTES: Dict[str, Tuple[Callable[..., Any], Dict[Any, Any]]] = {
            "/eel": (self._websocket, dict(websocket=True)),
            "/eel.js": (self._eel, dict()),
            "/": (self._root, dict()),
            "/<path:path>": (self._static, dict()),
        }
    
    # ===============================================================================================


    # Public methods
    def expose(self, name_or_function: Optional[Callable[..., Any]] = None) -> Callable[..., Any]:
        '''Decorator to expose Python callables via Eel's JavaScript API.

        When an exposed function is called, a callback function can be passed
        immediately afterwards. This callback will be called asynchronously with
        the return value (possibly `None`) when the Python function has finished
        executing.

        Blocking calls to the exposed function from the JavaScript side are only
        possible using the :code:`await` keyword inside an :code:`async function`.
        These still have to make a call to the response, i.e.
        :code:`await eel.py_random()();` inside an :code:`async function` will work,
        but just :code:`await eel.py_random();` will not.

        :Example:

        In Python do:

        .. code-block:: python

            @expose
            def say_hello_py(name: str = 'You') -> None:
                print(f'{name} said hello from the JavaScript world!')

        In JavaScript do:

        .. code-block:: javascript

            eel.say_hello_py('Alice')();

        Expected output on the Python console::

            Alice said hello from the JavaScript world!

        '''
        ic(f"expose: {name_or_function}")

        # Deal with '@eel.expose()' - treat as '@eel.expose'
        if name_or_function is None:
            return expose

        if isinstance(name_or_function, str):   # Called as '@eel.expose("my_name")'
            name = name_or_function

            def decorator(function: Callable[..., Any]) -> Any:
                self._expose(name, function)
                return function
            return decorator
        else:
            function = name_or_function
            self._expose(function.__name__, function)
            return function

    def init(self, 
            path: str,
            allowed_extensions: List[str] = ['.js', '.html', '.txt', '.htm', '.xhtml', '.vue'],
            js_result_timeout: int = 10000) -> None:
        '''Initialise Eel.

        This function should be called before :func:`start()` to initialise the
        parameters for the web interface, such as the path to the files to be
        served.

        :param path: Sets the path on the filesystem where files to be served to
            the browser are located, e.g. :file:`web`.
        :param allowed_extensions: A list of filename extensions which will be
            parsed for exposed eel functions which should be callable from python.
            Files with extensions not in *allowed_extensions* will still be served,
            but any JavaScript functions, even if marked as exposed, will not be
            accessible from python.
            *Default:* :code:`['.js', '.html', '.txt', '.htm', '.xhtml', '.vue']`.
        :param js_result_timeout: How long Eel should be waiting to register the
            results from a call to Eel's JavaScript API before before timing out.
            *Default:* :code:`10000` milliseconds.
        '''
        ic(f"init: {path}, {allowed_extensions}, {js_result_timeout}")
        # global root_path, _js_functions, _js_result_timeout
        self.root_path = self._get_real_path(path)

        js_functions = set()
        for root, _, files in os.walk(self.root_path):
            for name in files:
                if not any(name.endswith(ext) for ext in allowed_extensions):
                    continue

                try:
                    with open(os.path.join(root, name), encoding='utf-8') as file:
                        contents = file.read()
                        expose_calls = set()
                        matches = self.EXPOSED_JS_FUNCTIONS.parseString(contents).asList()
                        for expose_call in matches:
                            # Verify that function name is valid
                            msg = "eel.expose() call contains '(' or '='"
                            assert rgx.findall(r'[\(=]', expose_call) == [], msg
                            expose_calls.add(expose_call)
                        js_functions.update(expose_calls)
                except UnicodeDecodeError:
                    pass    # Malformed file probably

        self._js_functions = list(js_functions)
        for js_function in self._js_functions:
            self._mock_js_function(js_function)

        self._js_result_timeout = js_result_timeout


    async def start(self, 
            *start_urls: str,
            mode: Optional[Union[str, Literal[False]]] = 'chrome',
            host: str = '127.0.0.1',
            port: int = 8000,
            jinja_templates: Optional[str] = None,
            cmdline_args: List[str] = ['--disable-http-cache'],
            size: Optional[Tuple[int, int]] = None,
            position: Optional[Tuple[int, int]] = None,
            geometry: Dict[str, Tuple[int, int]] = {},
            close_callback: Optional[Callable[..., Any]] = None,
            app_mode: bool = True,
            all_interfaces: bool = False,
            disable_cache: bool = True,
            default_path: str = 'index.html',
            app: Quart = Quart(__name__), # btl.default_app(),
            shutdown_delay: float = 1.0,
            suppress_error: bool = False) -> None:
        '''Start the Eel app.

        Suppose you put all the frontend files in a directory called
        :file:`web`, including your start page :file:`main.html`, then the app
        is started like this:

        .. code-block:: python

            import eel
            eel.init('web')
            eel.start('main.html')

        This will start a webserver on the default settings
        (http://localhost:8000) and open a browser to
        http://localhost:8000/main.html.

        If Chrome or Chromium is installed then by default it will open that in
        *App Mode* (with the `--app` cmdline flag), regardless of what the OS's
        default browser is set to (it is possible to override this behaviour).

        :param mode: What browser is used, e.g. :code:`'chrome'`,
            :code:`'electron'`, :code:`'edge'`, :code:`'custom'`. Can also be
            `None` or `False` to not open a window. *Default:* :code:`'chrome'`.
        :param host: Hostname used for Bottle server. *Default:*
            :code:`'localhost'`.
        :param port: Port used for Bottle server. Use :code:`0` for port to be
            picked automatically. *Default:* :code:`8000`.
        :param jinja_templates: Folder for :mod:`jinja2` templates, e.g.
            :file:`my_templates`. *Default:* `None`.
        :param cmdline_args: A list of strings to pass to the command starting the
            browser. For example, we might add extra flags to Chrome with
            :code:`eel.start('main.html', mode='chrome-app', port=8080,
            cmdline_args=['--start-fullscreen', '--browser-startup-dialog'])`.
            *Default:* :code:`[]`.
        :param size: Tuple specifying the (width, height) of the main window in
            pixels. *Default:* `None`.
        :param position: Tuple specifying the (left, top) position of the main
            window in pixels. *Default*: `None`.
        :param geometry: A dictionary of specifying the size/position for all
            windows. The keys should be the relative path of the page, and the
            values should be a dictionary of the form
            :code:`{'size': (200, 100), 'position': (300, 50)}`. *Default:*
            :code:`{}`.
        :param close_callback: A lambda or function that is called when a websocket
            or window closes (i.e. when the user closes the window). It should take
            two arguments: a string which is the relative path of the page that
            just closed, and a list of the other websockets that are still open.
            *Default:* `None`.
        :param app_mode: Whether to run Chrome/Edge in App Mode. You can also
            specify *mode* as :code:`mode='chrome-app'` as a shorthand to start
            Chrome in App Mode.
        :param all_interfaces: Whether to allow the :mod:`bottle` server to listen
            for connections on all interfaces.
        :param disable_cache: Sets the no-store response header when serving
            assets.
        :param default_path: The default file to retrieve for the root URL.
        :param app: An instance of :class:`Quart` which will be used rather
            than creating a fresh one. This can be used to install middleware on
            the instance before starting Eel, e.g. for session management,
            authentication, etc. If *app* is not a :class:`bottle.Bottle` instance,
            you will need to call :code:`eel.register_eel_routes(app)` on your
            custom app instance.
        :param shutdown_delay: Timer configurable for Eel's shutdown detection
            mechanism, whereby when any websocket closes, it waits *shutdown_delay*
            seconds, and then checks if there are now any websocket connections.
            If not, then Eel closes. In case the user has closed the browser and
            wants to exit the program. *Default:* :code:`1.0` seconds.
        :param suppress_error: Temporary (suppressible) error message to inform
            users of breaking API change for v1.0.0. Set to `True` to suppress
            the error message.
        '''
        ic(f"start: {start_urls}")
        self._start_args.update({
            'mode': mode,
            'host': host,
            'port': port,

            'jinja_templates': jinja_templates,
            'cmdline_args': cmdline_args,
            'size': size,
            'position': position,
            'geometry': geometry,
            'close_callback': close_callback,
            'app_mode': app_mode,
            'all_interfaces': all_interfaces,
            'disable_cache': disable_cache,
            'default_path': default_path,
            'app': app,
            'shutdown_delay': shutdown_delay,
            'suppress_error': suppress_error,
        })
        pprint(self._start_args)

        ic(f"    start socket")
        if self._start_args['port'] == 0:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('localhost', 0))
            _start_args['port'] = sock.getsockname()[1]
            sock.close()

        ic(f"    start jinja_templates")
        if self._start_args['jinja_templates'] is not None:
            from jinja2 import Environment, FileSystemLoader, select_autoescape
            if not isinstance(self._start_args['jinja_templates'], str):
                raise TypeError("'jinja_templates' start_arg/option must be of type str")
            templates_path = os.path.join(root_path, self._start_args['jinja_templates'])
            self._start_args['jinja_env'] = Environment(
                loader=FileSystemLoader(templates_path),
                autoescape=select_autoescape(['html', 'xml'])
            )

        # verify shutdown_delay is correct value
        if not isinstance(self._start_args['shutdown_delay'], (int, float)):
            raise ValueError(
                '`shutdown_delay` must be a number, '
                'got a {}'.format(type(self._start_args['shutdown_delay']))
            )

        ic(f"    start show")
        # Launch the browser to the starting URLs
        self.show(*start_urls)



        # def run_lambda() -> None:
        ic(f"        run_lambda")
        if self._start_args['all_interfaces'] is True:
            HOST = '0.0.0.0'
        else:
            if not isinstance(self._start_args['host'], str):
                raise TypeError("'host' start_arg/option must be of type str")
            HOST = self._start_args['host']

        self.app = self._start_args['app']

        if isinstance(app, Quart):
            self.register_eel_routes(app)
        else:
            self.register_eel_routes(btl.default_app())

        ic(f"        run_lambda startup")
        await app.startup()
        ic(f"        run_lambda run_task")
        asyncio.create_task(
            self.app.run_task(
                host=HOST,
                port=self._start_args['port'],
            )
        )  # Non-blocking




    def show(self, *start_urls: str) -> None:
        ic(f"show: {start_urls}")
        '''Show the specified URL(s) in the browser.

        Suppose you have two files in your :file:`web` folder. The file
        :file:`hello.html` regularly includes :file:`eel.js` and provides
        interactivity, and the file :file:`goodbye.html` does not include
        :file:`eel.js` and simply provides plain HTML content not reliant on Eel.

        First, we defien a callback function to be called when the browser
        window is closed:

        .. code-block:: python

            def last_calls():
               eel.show('goodbye.html')

        Now we initialise and start Eel, with a :code:`close_callback` to our
        function:

        ..code-block:: python

            eel.init('web')
            eel.start('hello.html', mode='chrome-app', close_callback=last_calls)

        When the websocket from :file:`hello.html` is closed (e.g. because the
        user closed the browser window), Eel will wait *shutdown_delay* seconds
        (by default 1 second), then call our :code:`last_calls()` function, which
        opens another window with the :file:`goodbye.html` shown before our Eel app
        terminates.

        :param start_urls: One or more URLs to be opened.
        '''
        brw.open(list(start_urls), self._start_args)


    # def sleep(self, seconds: Union[int, float]) -> None:
        # '''A non-blocking sleep call compatible with the Gevent event loop.

        # .. note::
            # While this function simply wraps :func:`gevent.sleep()`, it is better
            # to call :func:`eel.sleep()` in your eel app, as this will ensure future
            # compatibility in case the implementation of Eel should change in some
            # respect.

        # :param seconds: The number of seconds to sleep.
        # '''
        # self.gvt.sleep(seconds)


    # def spawn(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> gvt.Greenlet:
        # '''Spawn a new Greenlet.

        # Calling this function will spawn a new :class:`gevent.Greenlet` running
        # *function* asynchronously.

        # .. caution::
            # If you spawn your own Greenlets to run in addition to those spawned by
            # Eel's internal core functionality, you will have to ensure that those
            # Greenlets will terminate as appropriate (either by returning or by
            # being killed via Gevent's kill mechanism), otherwise your app may not
            # terminate correctly when Eel itself terminates.

        # :param function: The function to be called and run as the Greenlet.
        # :param *args: Any positional arguments that should be passed to *function*.
        # :param **kwargs: Any key-word arguments that should be passed to
            # *function*.
        # '''
        # return gvt.spawn(function, *args, **kwargs)


    # Bottle Routes


    async def _eel(self) -> str:
        ic(f"_eel")
        start_geometry = {'default': {'size': self._start_args['size'],
                                      'position': self._start_args['position']},
                          'pages':   self._start_args['geometry']}

        page = self._eel_js.replace('/** _py_functions **/',
                               '_py_functions: %s,' % list(self._exposed_functions.keys()))
        page = page.replace('/** _start_geometry **/',
                            '_start_geometry: %s,' % self._safe_json(start_geometry))
        # btl.response.content_type = 'application/javascript'
        # self._set_response_headers(btl.response)
        # return page
        return Response(page, mimetype="application/javascript")


    async def _root(self) -> btl.Response:
        ic(f"_root")
        if not isinstance(self._start_args['default_path'], str):
            raise TypeError("'default_path' start_arg/option must be of type str")
        return self._static(self._start_args['default_path'])


    async def _static(self, path: str) -> btl.Response:
        ic(f"_static: {path}")
        response = None
        if 'jinja_env' in self._start_args and 'jinja_templates' in self._start_args:
            if not isinstance(self._start_args['jinja_templates'], str):
                raise TypeError("'jinja_templates' start_arg/option must be of type str")
            template_prefix = self._start_args['jinja_templates'] + '/'
            if path.startswith(template_prefix):
                n = len(template_prefix)
                template = self._start_args['jinja_env'].get_template(path[n:])
                response = btl.HTTPResponse(template.render())

        if response is None:
            # response = btl.static_file(path, root=self.root_path)
            return await send_from_directory(self.root_path, path)

        self._set_response_headers(response)
        return response


    # def _websocket(self, ws: WebSocketT) -> None:
    async def _websocket(self) -> None:
        print("\n############################################################ \n")
        ic(f"_websocket")
        
        ws = websocket._get_current_object()

        for js_function in self._js_functions:
            await self._import_js_function(js_function)

        # data = await websocket.receive()
        # await websocket.send(f"Echo: {data}")

        # Get query param (like page)
        page = websocket.args.get("page", "default")
        # page = btl.request.query.page
        if page not in self._mock_queue_done:
            for call in self._mock_queue:
                _self.repeated_send(ws, self._safe_json(call))
            self._mock_queue_done.add(page)

        self._websockets.append((page, ws))

        try:
            while True:
                msg = await websocket.receive()
                ic(f"_websocket receive = {msg}")
                if msg is not None:
                    message = jsn.loads(msg)
                    # spawn(self._process_message, message, ws)
                    await self._process_message(message, ws)
                else:
                    self._websockets.remove((page, ws))
                    break
        except Exception as e:
            ic(f"_websocket Exception = {e}")
        finally:
            self._websockets.remove((page, websocket._get_current_object()))
            await self._websocket_close(page)
            # self._websocket_close(page)

    def register_eel_routes(self, app: Quart) -> None:
        ic(f"register_eel_routes:")
        '''Register the required eel routes with `app`.

        .. note::

            :func:`eel.register_eel_routes()` is normally invoked implicitly by
            :func:`eel.start()` and does not need to be called explicitly in most
            cases. Registering the eel routes explicitly is only needed if you are
            passing something other than an instance of :class:`bottle.Bottle` to
            :func:`eel.start()`.

        :Example:

            >>> app = Quart()
            >>> eel.register_eel_routes(app)
            >>> middleware = beaker.middleware.SessionMiddleware(app)
            >>> eel.start(app=middleware)

        '''
        for route_path, route_params in self.BOTTLE_ROUTES.items():
            route_func, route_kwargs = route_params
            print(f"    app.add_url_rule({route_path}, view_func={route_func}, {route_kwargs})")
            app.add_url_rule(route_path, view_func=route_func, **route_kwargs)


    # Private functions


    def _safe_json(self, obj: Any) -> str:
        ic(f"_safe_json: {obj}")
        return jsn.dumps(obj, default=lambda o: None)


    async def _repeated_send(self, ws: Websocket, msg: str) -> None:
        ic(f"_repeated_send: {msg}")
        for attempt in range(100):
            try:
                await ws.send(msg)
                break
            except Exception:
                sleep(0.001)


    async def _process_message(self, message: Dict[str, Any], ws: Websocket) -> None:
        ic(f"_process_message: {message}")
        if 'call' in message:
            error_info = {}
            try:
                return_val = self._exposed_functions[message['name']](*message['args'])
                status = 'ok'
            except Exception as e:
                err_traceback = traceback.format_exc()
                traceback.print_exc()
                return_val = None
                status = 'error'
                error_info['errorText'] = repr(e)
                error_info['errorTraceback'] = err_traceback
            await self._repeated_send(ws, self._safe_json({ 'return': message['call'],
                                            'status': status,
                                            'value': return_val,
                                            'error': error_info,}))
        elif 'return' in message:
            call_id = message['return']
            if call_id in self._call_return_callbacks:
                callback, error_callback = self._call_return_callbacks.pop(call_id)
                if message['status'] == 'ok':
                    callback(message['value'])
                elif message['status'] == 'error' and error_callback is not None:
                    error_callback(message['error'], message['stack'])
            else:
                self._call_return_values[call_id] = message['value']

        else:
            ic('Invalid message received: ', message)


    def _get_real_path(self, path: str) -> str:
        ic(f"_get_real_path: {path}")
        if getattr(sys, 'frozen', False):
            return os.path.join(sys._MEIPASS, path)  # type: ignore # sys._MEIPASS is dynamically added by PyInstaller
        else:
            return os.path.abspath(path)


    def _mock_js_function(self, f: str) -> None:
        ic(f"_mock_js_function: {f}")
        exec('%s = lambda *args: _mock_call("%s", args)' % (f, f), globals())

    async def _import_js_function(self, f: str):
        # Create an async function dynamically
        async def dynamic_func(*args):
            return await self._js_call(f, args)

        # Attach it to the instance
        setattr(self, f, dynamic_func)
        # self._registered.append(f)


    # async def _import_js_function(self, f: str) -> None:
        # ic(f"_import_js_function: {f}")
        # exec('%s = lambda *args: _js_call("%s", args)' % (f, f), globals())


    async def _call_object(self, name: str, args: Any) -> Dict[str, Any]:
        ic(f"_call_object: {name}, {args}")
        self._call_number += 1
        call_id = self._call_number + rnd.random()
        return {'call': call_id, 'name': name, 'args': args}


    async def _mock_call(self, name: str, args: Any) -> Callable[[Optional[Callable[..., Any]], Optional[Callable[..., Any]]], Any]:
        ic(f"_mock_call: {name}, {args}")
        call_object = await self._call_object(name, args)
        self._mock_queue += [call_object]
        return await self._call_return(call_object)


    async def _js_call(self, name: str, args: Any) -> Callable[[Optional[Callable[..., Any]], Optional[Callable[..., Any]]], Any]:
        ic(f"_js_call: {name}, {args}")
        call_object = await self._call_object(name, args)
        for _, ws in self._websockets:
            await self._repeated_send(ws, self._safe_json(call_object))
        return await self._call_return(call_object)


    async def _call_return(self, call: Dict[str, Any]) -> Callable[[Optional[Callable[..., Any]], Optional[Callable[..., Any]]], Any]:
        ic(f"_call_return: {call}")
        call_id = call['call']

        def return_func(callback: Optional[Callable[..., Any]] = None,
                        error_callback: Optional[Callable[..., Any]] = None) -> Any:
            if callback is not None:
                _call_return_callbacks[call_id] = (callback, error_callback)
            else:
                for w in range(self._js_result_timeout):
                    if call_id in _call_return_values:
                        return _call_return_values.pop(call_id)
                    sleep(0.001)
        return return_func


    def _expose(self, name: str, function: Callable[..., Any]) -> None:
        ic(f"_expose: {name}")
        msg = 'Already exposed function with name "%s"' % name
        assert name not in self._exposed_functions, msg
        self._exposed_functions[name] = function


    def _detect_shutdown(self) -> None:
        ic(f"_detect_shutdown")
        if len(self._websockets) == 0:
            sys.exit()


    async def _websocket_close(self, page: str) -> None:
        ic(f"_websocket_close page")

        close_callback = self._start_args.get('close_callback')

        if close_callback is not None:
            if not callable(close_callback):
                raise TypeError("'close_callback' start_arg/option must be callable or None")
            sockets = [p for _, p in self._websockets]
            close_callback(page, sockets)
        else:
            # if isinstance(self._shutdown, gvt.Greenlet):
                # self._shutdown.kill()

            # self._shutdown = gvt.spawn_later(_start_args['shutdown_delay'], _detect_shutdown)
            quit()


    def _set_response_headers(self, response: btl.Response) -> None:
        ic(f"_set_response_headers: {response}")
        if self._start_args['disable_cache']:
            # https://stackoverflow.com/a/24748094/280852
            response.set_header('Cache-Control', 'no-store')
