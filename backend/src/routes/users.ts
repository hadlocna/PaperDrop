import { Router } from 'express';
import { registerUser, getUser } from '../controllers/userController';

const router = Router();

router.post('/', registerUser);
router.get('/:id', getUser);

export default router;
