import { Request, Response, NextFunction } from 'express';
import { flightService } from '../services/flight.service';
import { SelectFlightRequestSchema } from '../schemas/flight.schema';
import { BadRequestError } from '../lib/errors';

export class FlightController {
  async triggerSearch(req: Request, res: Response, next: NextFunction) {
    try {
      const user = (req as any).user;
      const tripId = req.params.id || req.params.tripId;
      const result = await flightService.triggerFlightSearch(tripId, user.id);
      res.status(202).json(result);
    } catch (err) {
      next(err);
    }
  }

  async getFlightOptions(req: Request, res: Response, next: NextFunction) {
    try {
      const user = (req as any).user;
      const tripId = req.params.id || req.params.tripId;
      const result = await flightService.getFlightOptions(tripId, user.id);
      res.json(result);
    } catch (err) {
      next(err);
    }
  }

  async selectFlight(req: Request, res: Response, next: NextFunction) {
    try {
      const user = (req as any).user;
      const tripId = req.params.id || req.params.tripId;

      const parsed = SelectFlightRequestSchema.safeParse(req.body);
      if (!parsed.success) {
        throw new BadRequestError('Invalid flight selection payload', parsed.error.issues);
      }

      const result = await flightService.selectFlight(tripId, user.id, parsed.data.flight);
      res.status(200).json(result);
    } catch (err) {
      next(err);
    }
  }
}

export const flightController = new FlightController();
