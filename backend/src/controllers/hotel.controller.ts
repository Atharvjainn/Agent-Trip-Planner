import { Request, Response, NextFunction } from 'express';
import { hotelService } from '../services/hotel.service';
import { SelectHotelRequestSchema, PatchStayBudgetSchema } from '../schemas/hotel.schema';
import { BadRequestError } from '../lib/errors';

export class HotelController {
  async triggerSearch(req: Request, res: Response, next: NextFunction) {
    try {
      const user = (req as any).user;
      const tripId = req.params.id || req.params.tripId;
      const result = await hotelService.triggerHotelSearch(tripId, user.id);
      res.status(202).json(result);
    } catch (err) {
      next(err);
    }
  }

  async getHotelOptions(req: Request, res: Response, next: NextFunction) {
    try {
      const user = (req as any).user;
      const tripId = req.params.id || req.params.tripId;
      const result = await hotelService.getHotelOptions(tripId, user.id);
      res.json(result);
    } catch (err) {
      next(err);
    }
  }

  async selectHotel(req: Request, res: Response, next: NextFunction) {
    try {
      const user = (req as any).user;
      const tripId = req.params.id || req.params.tripId;

      const parsed = SelectHotelRequestSchema.safeParse(req.body);
      if (!parsed.success) {
        throw new BadRequestError('Invalid hotel selection payload', parsed.error.issues);
      }

      const result = await hotelService.selectHotel(tripId, user.id, parsed.data.hotel);
      res.status(200).json(result);
    } catch (err) {
      next(err);
    }
  }

  async updateStayBudget(req: Request, res: Response, next: NextFunction) {
    try {
      const user = (req as any).user;
      const tripId = req.params.id || req.params.tripId;

      const parsed = PatchStayBudgetSchema.safeParse(req.body);
      if (!parsed.success) {
        throw new BadRequestError('Invalid stay budget payload', parsed.error.issues);
      }

      const result = await hotelService.updateStayBudget(
        tripId,
        user.id,
        parsed.data.stayBudgetMinor
      );
      res.status(200).json(result);
    } catch (err) {
      next(err);
    }
  }
}

export const hotelController = new HotelController();
