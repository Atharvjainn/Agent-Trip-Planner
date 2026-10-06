import { prisma } from '../lib/prisma';

export interface CreateJobDto {
  id: string;
  tripId: string;
  userId: string;
  name: string;
  status?: string;
}

export class JobRepository {
  async create(data: CreateJobDto) {
    return prisma.job.create({
      data: {
        id: data.id,
        tripId: data.tripId,
        userId: data.userId,
        name: data.name,
        status: data.status || 'queued',
      },
    });
  }

  async updateStatus(id: string, status: string, error?: string | null) {
    return prisma.job.update({
      where: { id },
      data: {
        status,
        error: error !== undefined ? error : undefined,
      },
    });
  }

  async findByIdAndUser(id: string, userId: string) {
    return prisma.job.findFirst({
      where: {
        id,
        userId,
      },
    });
  }

  async findLatestPendingByTripId(tripId: string, userId: string) {
    return prisma.job.findFirst({
      where: {
        tripId,
        userId,
        status: { in: ['queued', 'active'] },
      },
      orderBy: { createdAt: 'desc' },
      select: {
        id: true,
        name: true,
        status: true,
      },
    });
  }
}

export const jobRepository = new JobRepository();
