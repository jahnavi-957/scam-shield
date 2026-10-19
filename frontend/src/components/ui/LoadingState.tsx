import { ReactNode } from 'react';
import { cn } from '../../lib/utils';

export interface LoadingStateProps {
  label?: string;
  description?: string;
  className?: string;
}

export function LoadingState({
  label = 'Checking…',
  description,
  className,
}: LoadingStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-16 text-center',
        className,
      )}
    >
      <span
        className="h-7 w-7 animate-pulse-soft rounded-full bg-accent/25"
        aria-hidden="true"
      />
      <p className="mt-4 text-base font-medium text-ink">{label}</p>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-ink-faint">{description}</p>
      )}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-bg-soft', className)}
      aria-hidden="true"
    />
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn('h-5 w-5 animate-spin text-accent', className)}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="3"
      />
      <path
        className="opacity-90"
        fill="currentColor"
        d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-xl border border-line bg-bg-elevated px-6 py-14 text-center',
        className,
      )}
    >
      {icon && (
        <span className="text-ink-faint" aria-hidden="true">
          {icon}
        </span>
      )}
      <h3 className="mt-4 text-lg font-semibold tracking-tight text-ink">
        {title}
      </h3>
      {description && (
        <p className="mt-1.5 max-w-sm text-sm text-ink-faint">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}