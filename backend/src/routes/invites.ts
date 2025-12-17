import { Router } from 'express';
import { acceptInvite, createInvite, getInviteDetails } from '../controllers/inviteController';

const router = Router();

router.post('/devices/:id/invites', createInvite);
router.get('/:token', getInviteDetails);
router.post('/:token/accept', acceptInvite);

export default router;
