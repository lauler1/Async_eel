import os, random, asyncio
from async_eel.async_eel import AsyncEel

eel = AsyncEel()
# Set web files folder
eel.init('web')

@eel.expose
def pick_file(folder):
    print(f"pick_file({folder})")
    if os.path.isdir(folder):
        return random.choice(os.listdir(folder))
    else:
        return 'Not valid folder'

async def main():
    await eel.start('file_access.html', size=(300, 200))  # Start
    await eel.wait_ws_started # Wait till Websocket is up and running.


    print(f"Close the window to finish.")
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())