import random, os, sys, asyncio
from icecream import IceCreamDebugger
ic = IceCreamDebugger(prefix=f"callbacks|")

from async_eel.async_eel import AsyncEel

ic("------------------------------------------------------------------------------------------------")
eel = AsyncEel()
eel.init('web')

async def close_callback(page, sockets):
    """
    Optional callback for websocket close
    """
    print(f"close_callback({page}, {sockets}): websocket is closed")

@eel.expose
async def py_random():
    return random.random()

@eel.expose
async def py_exception(error):
    print(f"py_exception({error})")
    if error:
        raise ValueError("Test")
        # return "Error"
    else:
        return "No Error"

async def print_num(n):
    print('print_num: Got this from Javascript:', n)


async def print_num_failed(error, stack):
    print("This is an example of what javascript errors would look like:")
    print("\tError: ", error)
    print("\tStack: ", stack)

async def main():

    await eel.start('callbacks.html', size=(400, 300), close_callback=close_callback)
    await eel.wait_ws_started # Wait till Websocket is up and running.

    # Call Javascript function, and pass explicit callback function    
    eel.js_random().then_call(print_num)

    result = await eel.js_random().wait_answer()
    print(f"result -", result)

    # Do the same with an inline callback
    eel.js_random().then_call(lambda n: print('Got this from Javascript:', n))

    # Show error handling
    eel.js_with_error().then_call(print_num, print_num_failed)

    print(f"Close the window to finish.")
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())

