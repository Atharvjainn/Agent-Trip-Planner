import { betterAuth } from 'better-auth';
import { prismaAdapter } from 'better-auth/adapters/prisma';
import { prisma } from './prisma';

export const auth = betterAuth({
  database: prismaAdapter(prisma, {
    provider: 'postgresql',
  }),
  emailAndPassword: {
    enabled: true,
  },
  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID || '',
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || '',
    },
  },
  trustedOrigins: async (request) => {
    const origin = request?.headers?.get('origin');
    const origins = [
      process.env.FRONTEND_URL || 'http://localhost:3000',
      'http://localhost:3000',
      'http://localhost:*',
      'http://127.0.0.1:3000',
      'http://127.0.0.1:*',
      'http://192.168.1.45:3000',
      'http://192.168.*',
      ...(process.env.TRUSTED_ORIGINS ? process.env.TRUSTED_ORIGINS.split(',').map((s) => s.trim()) : []),
    ];
    if (origin && !origins.includes(origin)) {
      origins.push(origin);
    }
    return origins;
  },
});
