import random, os, sys, asyncio
from icecream import ic

lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../async_eel'))
sys.path.insert(0, lib_path)
from async_eel import AsyncEel

# ic.configureOutput(prefix='sync_callbacks| ')

print()
print()
print("------------------------------------------------------------------------------------------------")
eel = AsyncEel()
eel.init('web')

@eel.expose
def py_random():
    rnd = random.random()
    ic(f"py_random() = {rnd}")
    return random.random()

async def main():

    print(" ------------------------------------------------------------------ 1")
    await eel.start('sync_callbacks.html', size=(400, 300))

    print(" ------------------------------------------------------------------ 2")
    await asyncio.sleep(5)
    n = await eel.js_random()
    ic('Got this from Javascript:', n)

    count = 0
    while True:
        await asyncio.sleep(1)
        count += 1
        print(f"count = {count}")

    # Start Quart without blocking
    await app.startup()
    asyncio.create_task(app.run_task(host="0.0.0.0", port=5000))  # Non-blocking
    # asyncio.create_task(background_task())

    # Keep the loop alive
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
