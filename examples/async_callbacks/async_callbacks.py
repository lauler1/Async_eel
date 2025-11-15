import random, os, sys, asyncio
from icecream import ic

from async_eel.async_eel import AsyncEel

# ic.configureOutput(prefix='sync_callbacks| ')

async def close_callback(page, sockets):
    """
    Optional callback for websocket close
    """
    print(f"close_callback({page}, {sockets}): websocket is closed")
    
@AsyncEel.expose
def py_random():
    rnd = random.random()
    print(f"py_random() = {rnd}")
    return random.random()

async def main():
    print("------------------------------------------------------------------------------------------------")
    eel = AsyncEel()
    eel.init('web')

    await eel.start('sync_callbacks.html', size=(400, 300), close_callback=close_callback)
    
    print("Main: Current event loop:", id(asyncio.get_event_loop()))

    await eel.wait_ws_started # Wait till Websocket is up and running.
    
    n = await eel.js_random()()
    print('Got this from Javascript:', n)

    print(f"Close the window to finish.")
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
