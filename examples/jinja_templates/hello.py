import random, asyncio
from icecream import ic

from async_eel.async_eel import AsyncEel

eel = AsyncEel()
# Set web files folder
eel.init('web')

@eel.expose
def py_random():
    return random.random()

@eel.expose                         # Expose this function to Javascript
def say_hello_py(x):
    print('Hello from %s' % x)

async def main():

    say_hello_py('Python World!')
    eel.say_hello_js('Python World!')   # Call a Javascript function

    await eel.start('templates/hello.html', size=(300, 200), jinja_templates='templates')  # Start
    await eel.wait_ws_started # Wait till Websocket is up and running.

    print(f"Close the window to finish.")
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped by Ctrl+C")
