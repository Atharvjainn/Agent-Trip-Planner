import Redis from 'ioredis';
import { env } from '../config/env';
import { logger } from './logger';

export const redisConnection = new Redis(env.REDIS_URL, {
  maxRetriesPerRequest: null,
  enableReadyCheck: false,
  retryStrategy(times) {
    const delay = Math.min(times * 100, 3000);
    return delay;
  },
});

redisConnection.on('connect', () => {
  logger.info('Connected to Redis');
});

redisConnection.on('error', (err) => {
  logger.error('Redis connection error:', { error: err.message });
});
