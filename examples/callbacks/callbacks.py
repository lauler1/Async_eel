import random, os, sys, asyncio
from icecream import ic

lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../async_eel'))
sys.path.insert(0, lib_path)
from async_eel import AsyncEel

print("------------------------------------------------------------------------------------------------")
eel = AsyncEel()
eel.init('web')

def close_callback(page, sockets):
    print(f"close_callback({page}, {sockets})")

@eel.expose
def py_random():
    return random.random()

@eel.expose
def py_exception(error):
    print(f"py_exception({error})")
    if error:
        raise ValueError("Test")
        # return "Error"
    else:
        return "No Error"

def print_num(n):
    print('print_num: Got this from Javascript:', n)


def print_num_failed(error, stack):
    print("This is an example of what javascript errors would look like:")
    print("\tError: ", error)
    print("\tStack: ", stack)

async def main():

    await eel.start('callbacks.html', size=(400, 300))
    await asyncio.sleep(2)

    # Call Javascript function, and pass explicit callback function    
    await eel.js_random()(print_num)

    result = await eel.js_random()()
    print(f"result -", result)

    # Do the same with an inline callback
    await eel.js_random()(lambda n: print('Got this from Javascript:', n))

    # Show error handling
    await eel.js_with_error()(print_num, print_num_failed)

    print(f"Close the window to finish.")
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())

