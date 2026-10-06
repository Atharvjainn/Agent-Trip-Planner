'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { getJob } from '../lib/api/trips';
import { JobResponse } from '../lib/api/schemas';

interface UseJobOptions {
  pollingIntervalMs?: number;
  timeoutMs?: number;
  onCompleted?: (job: JobResponse) => void;
  onFailed?: (error: string) => void;
}

export function useJob(jobId: string | null | undefined, options: UseJobOptions = {}) {
  const {
    pollingIntervalMs = 1500,
    timeoutMs = 60000,
    onCompleted,
    onFailed,
  } = options;

  const [job, setJob] = useState<JobResponse | null>(null);
  const [status, setStatus] = useState<'idle' | 'queued' | 'active' | 'completed' | 'failed'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  const onCompletedRef = useRef(onCompleted);
  const onFailedRef = useRef(onFailed);

  useEffect(() => {
    onCompletedRef.current = onCompleted;
  }, [onCompleted]);

  useEffect(() => {
    onFailedRef.current = onFailed;
  }, [onFailed]);

  const retry = useCallback(() => {
    setError(null);
    setStatus('queued');
    setRetryCount((prev) => prev + 1);
  }, []);

  useEffect(() => {
    if (!jobId) {
      return;
    }

    let isMounted = true;
    const startTime = Date.now();
    let timerId: NodeJS.Timeout | null = null;

    const runPoll = async () => {
      if (!isMounted) return;

      if (Date.now() - startTime > timeoutMs) {
        if (timerId) clearInterval(timerId);
        if (!isMounted) return;
        setIsPolling(false);
        setStatus('failed');
        const timeoutMsg = 'This is taking longer than expected. Please retry.';
        setError(timeoutMsg);
        onFailedRef.current?.(timeoutMsg);
        return;
      }

      try {
        const data = await getJob(jobId);
        if (!isMounted) return;
        setJob(data);
        setStatus(data.status);

        if (data.status === 'completed') {
          if (timerId) clearInterval(timerId);
          setIsPolling(false);
          onCompletedRef.current?.(data);
        } else if (data.status === 'failed') {
          if (timerId) clearInterval(timerId);
          setIsPolling(false);
          const failureMsg = data.error || 'Failed to complete task. Please try again.';
          setError(failureMsg);
          onFailedRef.current?.(failureMsg);
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        console.error('Job polling error:', err);
      }
    };

    runPoll();
    timerId = setInterval(runPoll, pollingIntervalMs);

    return () => {
      isMounted = false;
      if (timerId) clearInterval(timerId);
      setIsPolling(false);
    };
  }, [jobId, retryCount, pollingIntervalMs, timeoutMs]);

  return {
    job,
    status,
    error,
    isPolling,
    retry,
  };
}
