
import os
import asyncio

async def ping(ip):
    proc = await asyncio.create_subprocess_exec(
        "ping", "-c", "1", "-W", "1", ip,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await proc.wait()
    if proc.returncode == 0:
        print(f"FOUND: {ip}")

async def main():
    print("Scanning 192.168.86.1-254...")
    tasks = []
    for i in range(1, 255):
        tasks.append(ping(f"192.168.86.{i}"))
    await asyncio.gather(*tasks)
    print("Scan complete.")

if __name__ == "__main__":
    asyncio.run(main())
