import { Router } from 'express';
import { claimDevice } from '../controllers/deviceController';

const router = Router();

router.post('/claim', claimDevice);

export default router;
