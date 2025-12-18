import asyncio
import subprocess

async def ping(ip):
    proc = await asyncio.create_subprocess_exec(
        "ping", "-c", "1", "-W", "200", ip,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await proc.wait()
    if proc.returncode == 0:
        print(f"Found device: {ip}")

async def main():
    print("Scanning 192.168.1.0/24...")
    tasks = []
    for i in range(1, 255):
        ip = f"192.168.1.{i}"
        tasks.append(ping(ip))
    await asyncio.gather(*tasks)
    print("Scan complete.")

if __name__ == "__main__":
    asyncio.run(main())
