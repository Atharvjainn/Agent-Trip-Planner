import { Request, Response } from 'express';
import { chatService } from '../services/chat.service';
import { ChatRequestInput } from '../schemas/chat.schema';

export async function sendMessageHandler(req: Request, res: Response) {
  const userId = req.user!.id;
  const tripId = typeof req.params.id === 'string' ? req.params.id : undefined;
  const input = req.body as ChatRequestInput;

  const result = await chatService.handleMessage(
    userId,
    input.message,
    tripId,
    input.sessionId,
    input.userLocation
  );

  return res.status(200).json({
    status: 'success',
    data: result,
  });
}

export async function createTripChatHandler(req: Request, res: Response) {
  const userId = req.user!.id;
  const input = req.body as ChatRequestInput;

  const result = await chatService.handleMessage(
    userId,
    input.message,
    undefined,
    input.sessionId,
    input.userLocation
  );

  return res.status(200).json({
    status: 'success',
    data: result,
  });
}
