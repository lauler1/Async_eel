# Eel Developers

## Setting up your environment

In order to start developing with Eel you'll need to checkout the code, set up a development and testing environment, and check that everything is in order.

### Clone the repository
```bash
git clone https://github.com/lauler1/Async_eel
```

### (Recommended) Create a virtual environment
It's recommended that you use virtual environments for this project. Your process for setting up a virutal environment will vary depending on OS and tool of choice, but might look something like this:

```bash
cd <Async_eel/>                 # If not yet
python3 -m venv venv
source venv/bin/activate
```

**Note**: `venv` is listed in the `.gitignore` file so it's the recommended virtual environment name
    

### Install project requirements

```bash
cd <Async_eel/>                 # If not yet
pip3 install -r requirements.txt        # eel's 'prod' requirements

```
### Install for local use with PIP

```bash
cd <Async_eel/>                 # If not yet
pip install -e .
```

### Enabling IceCream outputs.

In order to enable the IceCream debug outputs to the console, use:

```python
from async_eel.async_eel import ic_instances
ic_instances.enable_all()
#or
ic_instances.disable_all()
```
By default they are disabled.

## Call flow from Python to JS

<!--
```plantuml
@startuml
|Python App|

    start

    :eel.my_js_func;
    
    |Python AsyncEel|

    :_js_call;

    :async _repeat_send; <<task>>
    
    fork
    
		:_call_return;
    
    fork again

        |JS|

        :eel._websocket.onmessage;
        if(message.hasOwnProperty('call')) then (OK)
        :call(eel._exposed_functions(message.name));
        endif
        
        |Python AsyncEel|
          
        :async _websocket; <<task>>
        :async _process_message;
        
        
        if('return' in message) then (Yes)
          :call(eel._exposed_functions(message.name));
        
            if(call_id in self._call_return_callbacks) then (Yes)
                if(message['status'] == 'ok') then (Yes)
                :call(callback);
                else
                :call(error_callback);
                endif
                stop
            else
            :_call_return_values[call_id] = message['value'];
            endif
        else
          stop
        endif
    end fork

|Python App|

:res;

stop

@enduml

```
-->

![](./docs/call_python2js.png)