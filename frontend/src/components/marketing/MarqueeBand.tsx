import { cn } from '../../lib/utils';

export interface MarqueeBandProps {
  items: string[];
  className?: string;
}

export function MarqueeBand({ items, className }: MarqueeBandProps) {
  const doubled = [...items, ...items];
  return (
    <div className={cn('overflow-hidden border-y border-line bg-bg-soft/40 py-3', className)}>
      <div className="flex w-max animate-marquee-slow gap-8 whitespace-nowrap">
        {doubled.map((item, i) => (
          <span key={i} className="flex items-center gap-8 text-sm text-ink-faint">
            <span className="inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}