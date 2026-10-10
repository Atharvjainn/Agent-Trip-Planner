import { Request, Response } from 'express';
import { budgetService } from '../services/budget.service';
import { TripParams } from '../schemas/trip.schema';

export async function getTripBudgetHandler(req: Request, res: Response) {
  const userId = req.user!.id;
  const { id } = req.params as TripParams;
  const budget = await budgetService.getTripBudget(id, userId);

  return res.status(200).json({
    status: 'success',
    data: budget,
  });
}
