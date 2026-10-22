import { ReactNode } from 'react';
import { cn } from '../../lib/utils';

export interface EntityListItemProps {
  icon: ReactNode;
  label: string;
  value: string;
  meta?: ReactNode;
  className?: string;
}

export function EntityListItem({
  icon,
  label,
  value,
  meta,
  className,
}: EntityListItemProps) {
  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-lg border border-line bg-bg-soft/60 px-3.5 py-3',
        className,
      )}
    >
      <span
        className="mt-0.5 shrink-0 text-ink-faint"
        aria-hidden="true"
      >
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">
          {label}
        </p>
        <p className="mt-0.5 truncate text-sm font-medium text-ink" title={value}>
          {value}
        </p>
      </div>
      {meta && <div className="shrink-0 text-right">{meta}</div>}
    </div>
  );
}

export interface ListDividerProps {
  children?: ReactNode;
  className?: string;
}

export function ListDivider({ children, className }: ListDividerProps) {
  return (
    <div
      className={cn(
        'flex items-center gap-3 py-1 text-xs font-medium uppercase tracking-wide text-ink-faint',
        className,
      )}
    >
      <span className="h-px flex-1 bg-line" aria-hidden="true" />
      {children && <span>{children}</span>}
      <span className="h-px flex-1 bg-line" aria-hidden="true" />
    </div>
  );
}