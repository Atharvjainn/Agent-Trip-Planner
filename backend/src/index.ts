import express, { Request, Response } from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { toNodeHandler } from 'better-auth/node';
import { auth } from './lib/auth';
import { requireAuth, AuthenticatedRequest } from './middlewares/auth';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 5000;
const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:3000';

// CORS configuration (Essential for cookies/session headers)
app.use(
  cors({
    origin: FRONTEND_URL,
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'Cookie'],
  })
);

// Mount Better Auth handler for all /api/auth/* routes
// Note: Better Auth handles its own body parsing internally for auth routes
app.all('/api/auth/*', toNodeHandler(auth));

// Express body parsers for non-auth routes
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Public Routes
app.get('/', (req: Request, res: Response) => {
  res.json({
    status: 'success',
    message: 'Travel Planner Backend API is running!',
  });
});

app.get('/health', (req: Request, res: Response) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
  });
});

// Protected Route Example
app.get('/api/me', requireAuth, (req: AuthenticatedRequest, res: Response) => {
  res.json({
    status: 'success',
    user: req.user,
    session: req.session,
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
  console.log(`Auth endpoint ready at http://localhost:${PORT}/api/auth`);
});
