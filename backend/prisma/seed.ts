import { prisma } from '../src/lib/prisma';

async function main() {
    const device = await prisma.device.upsert({
        where: { deviceCode: 'SIM-001' },
        update: {},
        create: {
            deviceCode: 'SIM-001',
            deviceSecret: 'secret123',
            friendlyName: 'Simulation Device',
            id: 'SIM-DEVICE-001' // Matching the updated agent.py ID
        },
    });
    console.log('Seeded Device:', device);

    const device2 = await prisma.device.upsert({
        where: { deviceCode: 'CODE-1234' },
        update: {},
        create: {
            deviceCode: 'CODE-1234',
            deviceSecret: 'secret456',
            friendlyName: 'Example Device',
            id: 'EXAMPLE-DEVICE-001',
            status: 'setup_pending'
        },
    });
    console.log('Seeded Device 2:', device2);
}

main()
    .then(async () => {
        await prisma.$disconnect();
    })
    .catch(async (e) => {
        console.error(e);
        await prisma.$disconnect();
        process.exit(1);
    });
