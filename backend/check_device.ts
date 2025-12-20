import { PrismaClient } from '@prisma/client';
const prisma = new PrismaClient();

async function main() {
    const devices = await prisma.device.findMany({
        where: {
            deviceCode: {
                contains: '780420ea'
            }
        }
    });
    console.log(JSON.stringify(devices, null, 2));
}

main()
    .catch(e => {
        console.error(e);
        process.exit(1);
    })
    .finally(async () => {
        await prisma.$disconnect();
    });
