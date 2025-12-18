import { Router } from 'express';
import { acceptInvite, createInvite, getInviteDetails } from '../controllers/inviteController';
import { authenticateToken } from '../middleware/authMiddleware';

const router = Router();

router.post('/devices/:id/invites', authenticateToken, createInvite);
router.get('/:token', getInviteDetails);
router.post('/:token/accept', authenticateToken, acceptInvite);

export default router;
