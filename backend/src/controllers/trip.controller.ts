import { Request, Response } from 'express';
import { tripService } from '../services/trip.service';
import { CreateTripInput, TripParams } from '../schemas/trip.schema';

export async function createTripHandler(req: Request, res: Response) {
  const userId = req.user!.id;
  const input = req.body as CreateTripInput;
  const result = await tripService.createTrip(userId, input);

  return res.status(202).json({
    status: 'success',
    data: result,
  });
}

export async function getTripHandler(req: Request, res: Response) {
  const userId = req.user!.id;
  const { id } = req.params as TripParams;
  const trip = await tripService.getTripById(id, userId);

  return res.status(200).json({
    status: 'success',
    data: trip,
  });
}
