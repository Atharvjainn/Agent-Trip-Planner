import { app } from './app';
import { env } from './config/env';
import { logger } from './lib/logger';
import { prisma } from './lib/prisma';
import { redisConnection } from './lib/redis';
import { worker } from './worker';

const server = app.listen(env.PORT, () => {
  logger.info(`Server is running on http://localhost:${env.PORT}`);
  logger.info(`Auth endpoint ready at http://localhost:${env.PORT}/api/auth`);
});

async function gracefulShutdown(signal: string) {
  logger.info(`Received ${signal}. Shutting down gracefully...`);
  server.close(async () => {
    logger.info('HTTP server closed.');
    await worker.close();
    await prisma.$disconnect();
    await redisConnection.quit();
    logger.info('Database, Worker, and Redis connections closed.');
    process.exit(0);
  });
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));
