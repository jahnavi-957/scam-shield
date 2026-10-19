import { forwardRef } from 'react';
import { cn } from '../../lib/utils';

const inputBase =
  'w-full bg-bg-elevated border border-line rounded-md text-ink placeholder:text-ink-faint transition-colors focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent disabled:cursor-not-allowed disabled:bg-bg-soft';

const inputSizes: Record<string, string> = {
  sm: 'h-8 px-3 text-sm',
  md: 'h-11 px-4 text-base',
  lg: 'h-12 px-4 text-base',
};

export interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  size?: keyof typeof inputSizes;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, size = 'md', error, ...props }, ref) => {
    return (
      <div className="w-full">
        <input
          ref={ref}
          className={cn(
            inputBase,
            inputSizes[size],
            error && 'border-danger focus:ring-danger/30 focus:border-danger',
            className,
          )}
          {...props}
        />
        {error && (
          <p className="mt-1.5 text-sm text-danger">{error}</p>
        )}
      </div>
    );
  },
);
Input.displayName = 'Input';