import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
    const deviceCode = 'PD-780420ea';
    const newSecret = '78e89a81-74f6-4cb7-ad56-ff88466b68bb';

    try {
        const device = await prisma.device.update({
            where: { deviceCode },
            data: { deviceSecret: newSecret }
        });
        console.log('Successfully updated device secret for:', device.deviceCode);
        console.log('New Secret:', device.deviceSecret);
    } catch (err) {
        console.error('Error updating device secret:', err);
    } finally {
        await prisma.$disconnect();
    }
}

main();
