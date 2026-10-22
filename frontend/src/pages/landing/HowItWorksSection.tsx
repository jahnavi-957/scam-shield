import { cn } from '../../lib/utils';
import { useReveal } from '../../hooks/useReveal';

const steps = [
  {
    step: '01',
    title: 'Paste or drop',
    description: 'Paste a message or drag a screenshot into the input. No account, no setup.',
  },
  {
    step: '02',
    title: 'We analyze it',
    description: 'The message is classified and scanned for UPI IDs, phone numbers, URLs, and account details.',
  },
  {
    step: '03',
    title: 'Get a calm verdict',
    description: 'A clear verdict with the reasoning behind it, plus the entities found and their report history.',
  },
];

export default function HowItWorksSection() {
  const { ref, visible } = useReveal<HTMLDivElement>({ threshold: 0.12 });

  return (
    <section className="py-20 sm:py-28">
      <div className="container">
        <div ref={ref} className={cn('reveal max-w-2xl', visible && 'is-visible')}>
          <p className="text-meta">How it works</p>
          <h2 className="mt-3 text-headline">Three steps. No jargon.</h2>
          <p className="mt-4 text-body">
            We strip away the complexity. What you get is a fast, factual check
            you can act on immediately.
          </p>
        </div>

        <div className="mt-12 grid gap-6 sm:grid-cols-3">
          {steps.map((step) => (
            <div key={step.step} ref={ref} className={cn('reveal', visible && 'is-visible')}>
              <div className="rounded-xl border border-line bg-bg-elevated p-6 shadow-sm">
                <span className="text-xs font-semibold uppercase tracking-wide text-accent">
                  Step {step.step}
                </span>
                <h3 className="mt-3 text-lg font-semibold tracking-tight text-ink">{step.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">{step.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}