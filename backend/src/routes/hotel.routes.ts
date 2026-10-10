import { Router } from 'express';
import { hotelController } from '../controllers/hotel.controller';
import { requireAuth } from '../middlewares/auth';
import { asyncHandler } from '../lib/async-handler';

const router = Router({ mergeParams: true });

router.use(requireAuth);

router.post('/search', asyncHandler((req, res, next) =>
  hotelController.triggerSearch(req, res, next)
));

router.get('/', asyncHandler((req, res, next) =>
  hotelController.getHotelOptions(req, res, next)
));

router.post('/', asyncHandler((req, res, next) =>
  hotelController.selectHotel(req, res, next)
));

export default router;
