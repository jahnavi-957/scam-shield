import { forwardRef } from 'react';
import { cn } from '../../lib/utils';

const textareaBase =
  'w-full bg-bg-elevated border border-line rounded-md text-ink placeholder:text-ink-faint transition-colors focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-y';

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, ...props }, ref) => {
    return (
      <div className="w-full">
        <textarea
          ref={ref}
          className={cn(
            textareaBase,
            'min-h-[120px] p-4 text-base leading-relaxed',
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
Textarea.displayName = 'Textarea';