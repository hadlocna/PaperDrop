
import asyncio

IPS = [
    "192.168.86.23", "192.168.86.24", "192.168.86.22",
    "192.168.86.25", "192.168.86.237", "192.168.86.217",
    "192.168.86.64"
]

async def check_ssh(ip):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, 22), timeout=1.0
        )
        print(f"SSH OPEN: {ip}")
        writer.close()
        await writer.wait_closed()
    except:
        pass

async def main():
    tasks = [check_ssh(ip) for ip in IPS]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
