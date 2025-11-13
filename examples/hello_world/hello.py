import random, os, sys, asyncio
from icecream import ic

from async_eel.async_eel import AsyncEel

# lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../async_eel'))
# sys.path.insert(0, lib_path)
# from async_eel import AsyncEel

eel = AsyncEel()
# Set web files folder
eel.init('web')

@eel.expose                         # Expose this function to Javascript
def say_hello_py(x):
    print('Hello from %s' % x)

async def main():

    say_hello_py('Python World!')
    eel.say_hello_js('Python World!')   # Call a Javascript function

    await eel.start('hello.html', size=(300, 200))  # Start
    await eel.wait_ws_started # Wait till Websocket is up and running.


    print(f"Close the window to finish.")
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
