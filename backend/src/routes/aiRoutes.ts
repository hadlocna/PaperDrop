import { Router } from 'express';
import { AiController } from '../controllers/AiController';
import { authenticateToken } from '../middleware/authMiddleware';

const router = Router();

router.post('/generate', authenticateToken, AiController.generateDesign);

export default router;
