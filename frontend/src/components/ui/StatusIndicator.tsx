import { ReactNode } from 'react';
import { cn } from '../../lib/utils';

export type StatusTone = 'danger' | 'safe' | 'neutral' | 'accent';

const tones: Record<StatusTone, { dot: string; bg: string; text: string; border: string }> = {
  danger: {
    dot: 'bg-danger',
    bg: 'bg-danger-soft',
    text: 'text-danger-ink',
    border: 'border-danger/20',
  },
  safe: {
    dot: 'bg-safe',
    bg: 'bg-safe-soft',
    text: 'text-safe-ink',
    border: 'border-safe/20',
  },
  neutral: {
    dot: 'bg-neutral',
    bg: 'bg-neutral-soft',
    text: 'text-ink-soft',
    border: 'border-line',
  },
  accent: {
    dot: 'bg-accent',
    bg: 'bg-accent-soft',
    text: 'text-accent-ink',
    border: 'border-accent/20',
  },
};

export interface StatusIndicatorProps {
  tone: StatusTone;
  label: string;
  description?: string;
  icon?: ReactNode;
  className?: string;
}

export function StatusIndicator({
  tone,
  label,
  description,
  icon,
  className,
}: StatusIndicatorProps) {
  const t = tones[tone];
  return (
    <div
      className={cn(
        'inline-flex items-center gap-3 rounded-lg border px-3.5 py-2.5',
        t.bg, t.text, t.border, className,
      )}
    >
      <span className={cn('h-2.5 w-2.5 rounded-full', t.dot)} aria-hidden="true" />
      <div className="leading-tight">
        <p className="text-sm font-semibold tracking-tight">{label}</p>
        {description && (
          <p className="text-xs text-ink-faint">{description}</p>
        )}
      </div>
      {icon && <span className="ml-1 text-current" aria-hidden="true">{icon}</span>}
    </div>
  );
}

export interface BadgeProps {
  tone?: StatusTone;
  children: ReactNode;
  className?: string;
}

export function Badge({ tone = 'neutral', children, className }: BadgeProps) {
  const t = tones[tone];
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium',
        t.bg, t.text, className,
      )}
    >
      {children}
    </span>
  );
}