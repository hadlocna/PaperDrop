import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
    const deviceCode = 'PD-780420ea';
    const device = await prisma.device.findUnique({
        where: { deviceCode },
        include: { owner: true }
    });

    if (device) {
        console.log('Device found:');
        console.log(JSON.stringify(device, null, 2));
    } else {
        console.log('Device not found');
    }
}

main()
    .catch(e => console.error(e))
    .finally(async () => {
        await prisma.$disconnect();
    });
