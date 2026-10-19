import { ReactNode } from 'react';
import { cn } from '../../lib/utils';

export interface StatCardProps {
  value: string;
  label: string;
  className?: string;
}

export function StatCard({ value, label, className }: StatCardProps) {
  return (
    <div className={cn('text-center', className)}>
      <p className="text-3xl font-bold tracking-tight text-ink sm:text-4xl">{value}</p>
      <p className="mt-1 text-sm text-ink-faint">{label}</p>
    </div>
  );
}

export interface FeatureCardProps {
  icon: ReactNode;
  title: string;
  description: string;
  className?: string;
}

export function FeatureCard({ icon, title, description, className }: FeatureCardProps) {
  return (
    <div className={cn('rounded-xl border border-line bg-bg-elevated p-6 shadow-sm transition-shadow hover:shadow-md', className)}>
      <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-soft text-accent" aria-hidden="true">{icon}</span>
      <h3 className="mt-4 text-lg font-semibold tracking-tight text-ink">{title}</h3>
      <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">{description}</p>
    </div>
  );
}

export interface TestimonialCardProps {
  quote: string;
  name: string;
  company: string;
  className?: string;
}

export function TestimonialCard({ quote, name, company, className }: TestimonialCardProps) {
  const initials = name.split(' ').map((p) => p[0]).join('').slice(0, 2).toUpperCase();
  return (
    <div className={cn('flex h-full flex-col justify-between rounded-xl border border-line bg-bg-elevated p-6 shadow-sm', className)}>
      <p className="text-base leading-relaxed text-ink-soft">"{quote}"</p>
      <div className="mt-5 flex items-center gap-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-soft text-sm font-semibold text-accent-ink" aria-hidden="true">{initials}</span>
        <div>
          <p className="text-sm font-semibold text-ink">{name}</p>
          <p className="text-xs text-ink-faint">{company}</p>
        </div>
      </div>
    </div>
  );
}