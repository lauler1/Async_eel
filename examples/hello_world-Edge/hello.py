import random, os, sys, asyncio, platform
from icecream import ic

from async_eel.async_eel import AsyncEel

# # Use the same static files as the original Example
os.chdir(os.path.join('..', 'hello_world'))

eel = AsyncEel()

# Set web files folder and optionally specify which file types to check for eel.expose()
eel.init('web', allowed_extensions=['.js', '.html'])

@eel.expose                         # Expose this function to Javascript
def say_hello_py(x):
    print('Hello from %s' % x)

async def main():

    say_hello_py('Python World!')
    eel.say_hello_js('Python World!')   # Call a Javascript function

    # Launch example in Microsoft Edge only on Windows 10 and above
    if sys.platform in ['win32', 'win64'] and int(platform.release()) >= 10:
        await eel.start('hello.html', mode='edge', size=(300, 200))
    else:
        raise EnvironmentError('Error: System is not Windows 10 or above')
        sys.exit(0)

    await eel.wait_ws_started # Wait till Websocket is up and running.

    print(f"Close the window to finish.")
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
