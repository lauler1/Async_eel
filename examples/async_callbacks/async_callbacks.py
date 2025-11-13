import random, os, sys, asyncio
from icecream import ic

lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../async_eel'))
sys.path.insert(0, lib_path)
from async_eel import AsyncEel

# ic.configureOutput(prefix='sync_callbacks| ')

print("------------------------------------------------------------------------------------------------")
eel = AsyncEel()
eel.init('web')

def close_callback(page, sockets):
    print(f"close_callback({page}, {sockets})")
    
@eel.expose
def py_random():
    rnd = random.random()
    print(f"py_random() = {rnd}")
    return random.random()

async def main():

    await eel.start('sync_callbacks.html', size=(400, 300), close_callback=close_callback)

    await asyncio.sleep(2)
    n = await eel.js_random()()
    print('Got this from Javascript:', n)

    print(f"Close the window to finish.")
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
