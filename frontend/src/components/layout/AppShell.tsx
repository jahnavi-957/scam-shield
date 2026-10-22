import { ReactNode } from 'react';
import { cn } from '../../lib/utils';

export interface AppShellProps {
  children: ReactNode;
  className?: string;
}

export function AppShell({ children, className }: AppShellProps) {
  return (
    <div
      className={cn(
        'min-h-screen bg-bg text-ink antialiased',
        className,
      )}
    >
      {children}
    </div>
  );
}