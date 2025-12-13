import { Router } from 'express';
import { AiController } from '../controllers/AiController';

const router = Router();

router.post('/generate', AiController.generateDesign);

export default router;
