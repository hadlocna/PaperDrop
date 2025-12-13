"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
Object.defineProperty(exports, "__esModule", { value: true });
const prisma_1 = require("../src/lib/prisma");
function main() {
    return __awaiter(this, void 0, void 0, function* () {
        const device = yield prisma_1.prisma.device.upsert({
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
        const device2 = yield prisma_1.prisma.device.upsert({
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
    });
}
main()
    .then(() => __awaiter(void 0, void 0, void 0, function* () {
    yield prisma_1.prisma.$disconnect();
}))
    .catch((e) => __awaiter(void 0, void 0, void 0, function* () {
    console.error(e);
    yield prisma_1.prisma.$disconnect();
    process.exit(1);
}));
