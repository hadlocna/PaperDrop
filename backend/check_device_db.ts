import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
    const deviceCode = 'PD-780420ea';
    const device = await prisma.device.findUnique({
        where: { deviceCode }
    });

    if (device) {
        console.log('Device found:');
        console.log('ID:', device.id);
        console.log('Code:', device.deviceCode);
        console.log('Secret:', device.deviceSecret);
        console.log('Status:', device.status);
        console.log('Owner ID:', device.ownerId);
    } else {
        console.log('Device not found:', deviceCode);
    }
}

main()
    .catch(console.error)
    .finally(() => prisma.$disconnect());
