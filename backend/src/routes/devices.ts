import { Router } from 'express';
import {
    claimDevice,
    getDevices,
    getDevice,
    updateDevice,
    testPrint,
    getAccess,
    grantAccess,
    revokeAccess
} from '../controllers/deviceController';

const router = Router();

router.post('/claim', claimDevice);
router.get('/', getDevices);
router.get('/:id', getDevice);
router.patch('/:id', updateDevice);
router.post('/:id/test', testPrint);
router.get('/:id/access', getAccess);
router.post('/:id/access', grantAccess);
router.delete('/:id/access/:userId', revokeAccess);

export default router;
