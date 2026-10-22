import { cn } from '../../lib/utils';

export function Footer({ className }: { className?: string }) {
  return (
    <footer className={cn('mt-auto border-t border-line py-8', className)}>
      <div className="container flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-ink-faint">
          Scam Shield — a calm, factual check on messages before you act.
        </p>
        <p className="text-xs text-ink-faint">
          Powered by AI classification &amp; community reports.
        </p>
      </div>
    </footer>
  );
}