
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
    console.log('Start seeding...');

    const testDevice = await prisma.device.upsert({
        where: { deviceCode: 'TEST88' },
        update: {}, // No updates if exists
        create: {
            id: '7a46de1e-4c22-4902-9c8e-e5bcdae63c41', // Consistent UUID
            deviceCode: 'TEST88',
            deviceSecret: 'fake-secret-123',
            status: 'setup_pending',
            friendlyName: 'Test Device 88',
            // owner: undefined (unclaimed)
        },
    });

    console.log(`Seeded device: ${testDevice.deviceCode}`);
    console.log('Seeding finished.');
}

main()
    .catch((e) => {
        console.error(e);
        process.exit(1);
    })
    .finally(async () => {
        await prisma.$disconnect();
    });
