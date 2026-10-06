import express from 'express';
import cors from 'cors';
import { toNodeHandler } from 'better-auth/node';
import { auth } from './lib/auth';
import { env } from './config/env';
import routes from './routes';
import { errorHandler } from './middlewares/error-handler';

export const app = express();

// CORS configuration (Essential for cookies/session headers)
app.use(
  cors({
    origin: env.FRONTEND_URL,
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'Cookie'],
  })
);

// Mount Better Auth handler for all /api/auth/* routes
// Note: Better Auth handles its own body parsing internally for auth routes
app.all('/api/auth/*', toNodeHandler(auth));

// Express body parsers for non-auth routes
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Mount all application routes
app.use('/', routes);

// Global Error Handler
app.use(errorHandler);
