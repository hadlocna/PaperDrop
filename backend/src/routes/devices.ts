import { Router } from 'express';
import {
    claimDevice,
    getDevices,
    getDevice,
    updateDevice,
    testPrint,
    getAccess,
    grantAccess,
    revokeAccess,
    downloadLogs,
    unclaimDevice
} from '../controllers/deviceController';

import { authenticateToken } from '../middleware/authMiddleware';

const router = Router();

router.use(authenticateToken);

router.post('/claim', claimDevice);
router.delete('/:id/claim', unclaimDevice);
router.get('/', getDevices);
router.get('/:id', getDevice);
router.patch('/:id', updateDevice);
router.post('/:id/test', testPrint);
router.get('/:id/logs', downloadLogs);
router.get('/:id/access', getAccess);
router.post('/:id/access', grantAccess);
router.delete('/:id/access/:userId', revokeAccess);

export default router;
