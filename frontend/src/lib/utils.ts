import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function generateGoogleCalendarUrl(options: {
  title: string;
  startTime?: string | Date;
  durationMinutes?: number;
  description?: string;
  location?: string;
}): string {
  let start = new Date();
  if (options.startTime) {
    const parsed = new Date(options.startTime);
    if (!isNaN(parsed.getTime())) {
      start = parsed;
    }
  }
  const duration = options.durationMinutes || 30;
  const end = new Date(start.getTime() + duration * 60000);

  const formatUtc = (d: Date) => {
    return d.toISOString().replace(/-|:|\.\d+/g, '');
  };

  const dates = `${formatUtc(start)}/${formatUtc(end)}`;
  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: options.title,
    dates: dates,
    details: options.description || '',
    location: options.location || '',
  });

  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}
