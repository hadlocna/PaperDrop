import { Router } from 'express';
import { sendMessage, getMessages, clearQueue } from '../controllers/messageController';

const router = Router();

router.get('/', getMessages);
router.post('/', sendMessage);
router.delete('/queue', clearQueue);

export default router;
