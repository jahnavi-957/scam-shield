import { cn } from '../../lib/utils';
import { useReveal } from '../../hooks/useReveal';
import { Button } from '../../components/ui/Button';
import { useUiStore } from '../../store';
import { ShieldCheck, ArrowRight } from 'lucide-react';

export default function FinalCta() {
  const { goHome, goLookup } = useUiStore();
  const { ref, visible } = useReveal<HTMLDivElement>({ threshold: 0.12 });

  return (
    <section className="py-20 sm:py-28">
      <div className="container">
        <div
          ref={ref}
          className={cn(
            'reveal relative overflow-hidden rounded-2xl border border-line bg-bg-elevated px-8 py-16 text-center shadow-sm sm:px-16',
            visible && 'is-visible',
          )}
        >
          <div className="pointer-events-none absolute inset-0 -z-10">
            <div className="gradient-blob absolute -top-20 left-1/2 h-[22rem] w-[22rem] -translate-x-1/2" />
          </div>

          <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-accent-soft text-accent" aria-hidden="true">
            <ShieldCheck className="h-6 w-6" />
          </span>
          <h2 className="mt-5 text-3xl font-bold tracking-tight text-ink sm:text-4xl">
            Check your next message before you send money.
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-base text-ink-soft">
            It takes seconds, costs nothing, and requires no account. Paste a
            message or upload a screenshot and get a calm, factual verdict.
          </p>
          <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
            <Button variant="primary" size="lg" onClick={goHome}>
              Analyze a message
              <ArrowRight className="h-4 w-4" />
            </Button>
            <Button variant="secondary" size="lg" onClick={goLookup}>
              Look up an entity
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
