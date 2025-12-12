
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
    const devices = await prisma.device.findMany();
    console.log("--- DEVICES ---");
    devices.forEach(d => {
        console.log(`- [${d.deviceCode}] ${d.friendlyName || d.name || 'Unnamed'} (Online: ${d.isOnline}) - Seen: ${d.lastSeenAt}`);
    });
    console.log("----------------");
}

main()
    .catch(e => console.error(e))
    .finally(async () => await prisma.$disconnect());
