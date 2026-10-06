import { Request, Response } from 'express';
import { destinationService } from '../services/destination.service';
import { SelectDestinationInput } from '../schemas/destination.schema';
import { TripParams } from '../schemas/trip.schema';

export async function selectDestinationHandler(req: Request, res: Response) {
  const userId = req.user!.id;
  const { id } = req.params as TripParams;
  const input = req.body as SelectDestinationInput;

  const result = await destinationService.selectDestination(id, userId, input);

  return res.status(202).json({
    status: 'success',
    data: result,
  });
}
