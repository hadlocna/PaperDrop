import { Router } from 'express';
import { sendMessage, getMessages } from '../controllers/messageController';

const router = Router();

router.get('/', getMessages);
router.post('/', sendMessage);

export default router;
