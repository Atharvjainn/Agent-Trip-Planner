import Redis from 'ioredis';
import { env } from '../config/env';
import { logger } from './logger';

export const redisConnection = new Redis(env.REDIS_URL, {
  maxRetriesPerRequest: null,
  enableReadyCheck: false,
  family: 4, // Force IPv4 to avoid AAAA record lookup timeouts
  connectTimeout: 10000,
  keepAlive: 10000,
  retryStrategy(times) {
    const delay = Math.min(times * 500, 5000);
    return delay;
  },
});

redisConnection.on('connect', () => {
  logger.info('Connected to Redis');
});

redisConnection.on('error', (err) => {
  logger.error('Redis connection error:', { error: err.message });
});

export const redisClient = redisConnection;

