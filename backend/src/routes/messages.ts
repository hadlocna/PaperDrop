import { Router } from 'express';
import { authenticateToken } from '../middleware/authMiddleware';
import { sendMessage, getMessages, clearQueue } from '../controllers/messageController';

const router = Router();

router.use(authenticateToken);

router.get('/', getMessages);
router.post('/', sendMessage);
router.delete('/queue', clearQueue);

export default router;
