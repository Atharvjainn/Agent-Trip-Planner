import { prisma } from '../lib/prisma';

export interface CreateJobDto {
  id: string;
  tripId: string;
  userId: string;
  name: string;
  status?: string;
}

export class JobRepository {
  async create(
    dataOrId: CreateJobDto | string,
    tripId?: string,
    userId?: string,
    name?: string
  ) {
    if (typeof dataOrId === 'string') {
      return prisma.job.create({
        data: {
          id: dataOrId,
          tripId: tripId!,
          userId: userId!,
          name: name!,
          status: 'queued',
        },
      });
    }

    return prisma.job.create({
      data: {
        id: dataOrId.id,
        tripId: dataOrId.tripId,
        userId: dataOrId.userId,
        name: dataOrId.name,
        status: dataOrId.status || 'queued',
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

  async findLatestByTripAndName(tripId: string, name: string) {
    return prisma.job.findFirst({
      where: {
        tripId,
        name,
      },
      orderBy: { createdAt: 'desc' },
      select: {
        id: true,
        name: true,
        status: true,
        error: true,
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
