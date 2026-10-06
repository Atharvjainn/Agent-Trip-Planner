import { Request, Response } from 'express';
import { spotService } from '../services/spot.service';
import { SelectSpotsInput } from '../schemas/spot.schema';
import { TripParams } from '../schemas/trip.schema';

export async function selectSpotsHandler(req: Request, res: Response) {
  const userId = req.user!.id;
  const { id } = req.params as TripParams;
  const input = req.body as SelectSpotsInput;

  const result = await spotService.selectSpots(id, userId, input);

  return res.status(200).json({
    status: 'success',
    data: result,
  });
}
