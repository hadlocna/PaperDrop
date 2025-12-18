import { Router } from 'express';
import { registerUser, getUser } from '../controllers/userController';
import { authenticateToken } from '../middleware/authMiddleware';

const router = Router();

router.post('/', registerUser);
router.get('/:id', authenticateToken, getUser);

export default router;
