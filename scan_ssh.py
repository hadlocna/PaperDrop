import asyncio
import socket

async def check_ssh(ip):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, 22),
            timeout=1.0
        )
        print(f"SSH OPEN: {ip}")
        writer.close()
        await writer.wait_closed()
        return ip
    except:
        return None

async def main():
    print("Scanning 192.168.1.0/24 for SSH...")
    tasks = []
    for i in range(1, 255):
        ip = f"192.168.1.{i}"
        tasks.append(check_ssh(ip))
    
    results = await asyncio.gather(*tasks)
    found = [r for r in results if r]
    print(f"Scan complete. Found SSH on: {found}")

if __name__ == "__main__":
    asyncio.run(main())
