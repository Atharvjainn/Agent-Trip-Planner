import { Request, Response, NextFunction } from 'express';
import { summaryService } from '../services/summary.service';

export class SummaryController {
  async triggerBuildSummary(req: Request, res: Response, next: NextFunction) {
    try {
      const tripId = req.params.id as string;
      const userId = (req as any).user.id;
      const result = await summaryService.triggerBuildSummary(tripId, userId);
      res.status(202).json(result);
    } catch (err) {
      next(err);
    }
  }

  async getSummary(req: Request, res: Response, next: NextFunction) {
    try {
      const tripId = req.params.id as string;
      const userId = (req as any).user.id;
      const result = await summaryService.getSummary(tripId, userId);
      res.json(result);
    } catch (err) {
      next(err);
    }
  }
}

export const summaryController = new SummaryController();
