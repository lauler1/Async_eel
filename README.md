# Async Eel

This project is a fork of the [Python Eel](https://github.com/python-eel/Eel) library.

It provides an **asynchronous version** of Eel, built using the **Quart** server framework.

The source code can be found in the `async_eel/` directory.

A working example is available in `examples/async_callbacks/`.

This project does not yet have a PyPI (pip) installation package, but it is already functional for the provided example.

Feel free to contribute!

Call from Python to JS
```plantuml
@startuml
|Python App|
    start
    :eel.my_js_func;
    
    |Python AsyncEel|
    :_js_call;
    :async _repeat_send;
    
    fork
    :_call_return;
    
    fork again
        |JS|
        :eel._websocket.onmessage;
        if(message.hasOwnProperty('call')) then (OK)
        :call(eel._exposed_functions(message.name));
        endif
        
        |Python AsyncEel|
        :async _websocket;
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
