type LogLevel = 'info' | 'warn' | 'error' | 'debug';

function log(level: LogLevel, message: string, meta?: Record<string, any>) {
  const timestamp = new Date().toISOString();
  const metaStr = meta ? ` ${JSON.stringify(meta)}` : '';
  const formatted = `[${timestamp}] [${level.toUpperCase()}] ${message}${metaStr}`;

  if (level === 'error') {
    console.error(formatted);
  } else if (level === 'warn') {
    console.warn(formatted);
  } else {
    console.log(formatted);
  }
}

export const logger = {
  info: (msg: string, meta?: Record<string, any>) => log('info', msg, meta),
  warn: (msg: string, meta?: Record<string, any>) => log('warn', msg, meta),
  error: (msg: string, meta?: Record<string, any>) => log('error', msg, meta),
  debug: (msg: string, meta?: Record<string, any>) => log('debug', msg, meta),
};
