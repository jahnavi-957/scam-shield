import { ReactNode } from 'react';
import { cn } from '../../lib/utils';

export interface CardProps {
  children: ReactNode;
  className?: string;
  padding?: 'sm' | 'md' | 'lg';
}

const paddings: Record<string, string> = {
  sm: 'p-4',
  md: 'p-5',
  lg: 'p-7',
};

export function Card({ children, className, padding = 'md' }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-xl bg-bg-elevated shadow-sm',
        paddings[padding],
        className,
      )}
    >
      {children}
    </div>
  );
}