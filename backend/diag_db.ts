import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
    console.log('DATABASE_URL:', process.env.DATABASE_URL);
    try {
        const devices = await prisma.device.findMany();
        console.log('Devices found:', devices.length);
        devices.forEach(d => {
            console.log(`- ${d.deviceCode}: ${d.id} (${d.friendlyName})`);
        });

        const messages = await prisma.message.findMany({
            orderBy: { createdAt: 'desc' },
            take: 10
        });
        console.log('Recent messages (all devices):');
        messages.forEach(m => {
            console.log(`- ${m.id}: ${m.status} for device ${m.deviceId} (${m.contentType}) at ${m.createdAt}`);
        });
    } catch (err) {
        console.error('Error querying devices:', err);
    } finally {
        await prisma.$disconnect();
    }
}

main();
