import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
    const deviceCode = 'PD-780420ea';
    const userId = '2abad377-fcb5-4b79-b69f-144bd09ed94e'; // Owner ID from diag_db.ts

    try {
        const device = await prisma.device.findUnique({ where: { deviceCode } });
        if (!device) throw new Error('Device not found');

        const message = await prisma.message.create({
            data: {
                senderId: userId,
                deviceId: device.id,
                contentType: 'text',
                content: JSON.stringify({ body: 'Hello from Cascade! Connection fixed.' }),
                status: 'queued'
            }
        });
        console.log('Created test message:', message.id);
    } catch (err) {
        console.error('Error creating test message:', err);
    } finally {
        await prisma.$disconnect();
    }
}

main();
