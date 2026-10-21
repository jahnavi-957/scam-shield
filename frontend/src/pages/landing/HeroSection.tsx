import { useEffect, useRef, useState } from 'react';
import { useUiStore } from '../../store';
import { useAnalyzeText } from '../../hooks/mutations';
import { useReveal } from '../../hooks/useReveal';
import { cn } from '../../lib/utils';
import { Textarea } from '../../components/ui/Textarea';
import { Button } from '../../components/ui/Button';
import { ArrowRight, CheckCircle2, Image, Sparkles } from 'lucide-react';

export default function HeroSection() {
  const { goHome, goUpload, showResult, showError } = useUiStore();
  const mutation = useAnalyzeText();
  const { ref, visible } = useReveal<HTMLDivElement>({ threshold: 0.1 });

  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const handleSubmit = async () => {
    const trimmed = text.trim();
    if (!trimmed) {
      setError('Paste a message to analyze.');
      return;
    }
    setError(null);
    try {
      const result = await mutation.mutateAsync(trimmed);
      showResult({
        message_id: result.message_id,
        source: result.source,
        is_scam: result.is_scam,
        scam_type: result.scam_type,
        confidence: result.confidence,
        explanation: result.explanation,
        entities: result.entities,
        prior_reports: result.prior_reports,
        near_duplicates: result.near_duplicates,
        alert_triggered: result.alert_triggered,
        created_at: result.created_at,
        truncated: result.truncated,
        classifier_kind: result.classifier_kind,
        similarity_score: result.similarity_score,
        matched_scam_id: result.matched_scam_id,
      });
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Analysis failed. Please try again.');
    }
  };

  const handleReset = () => {
    mutation.reset();
    setText('');
    setError(null);
    goHome();
  };

  const isBusy = mutation.isPending;

  return (
    <section className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="gradient-blob absolute -top-24 left-1/2 h-[28rem] w-[28rem] -translate-x-1/2" />
        <div className="gradient-blob safe absolute -bottom-16 right-0 h-[24rem] w-[24rem]" />
      </div>

      <div className="container flex flex-col items-center py-20 text-center sm:py-28">
        <span
          ref={ref}
          className={cn(
            'reveal inline-flex items-center gap-2 rounded-full border border-line bg-bg-elevated px-3 py-1 text-xs font-medium text-ink-soft shadow-sm',
            visible && 'is-visible',
          )}
        >
          <Sparkles className="h-3.5 w-3.5 text-accent" /> Now checking screenshots too
        </span>

        <h1
          ref={ref}
          className={cn(
            'reveal mt-6 text-5xl font-bold tracking-tight text-ink sm:text-6xl lg:text-7xl',
            visible && 'is-visible',
          )}
        >
          Check a message <span className="text-accent">before</span> you act.
        </h1>

        <p
          ref={ref}
          className={cn(
            'reveal mx-auto mt-5 max-w-2xl text-lg leading-relaxed text-ink-soft sm:text-xl',
            visible && 'is-visible',
          )}
        >
          Scam Shield classifies messages and screenshots in seconds, flags
          known UPI IDs, phone numbers, and URLs, and gives you a calm,
          factual verdict so you can decide with confidence.
        </p>

        <div ref={ref} className={cn('reveal mt-9 w-full max-w-2xl', visible && 'is-visible')}>
          <Textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder="Paste a suspicious message here…"
            error={error ?? undefined}
            aria-label="Message to analyze"
            disabled={isBusy}
          />
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-ink-faint">
              Include sender names, UPI IDs, or links for the best result.
              Your message is sent to Scam Shield to provide this check. No account is required.
            </p>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={handleReset} disabled={!text}>
                Clear
              </Button>
              <Button variant="secondary" size="lg" onClick={goUpload} disabled={isBusy}>
                <Image className="h-4 w-4" /> Screenshot
              </Button>
              <Button variant="primary" size="lg" onClick={handleSubmit} disabled={isBusy}>
                {isBusy ? 'Analyzing…' : 'Analyze'}
                <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>

        <div
          ref={ref}
          className={cn(
            'reveal mt-10 flex flex-wrap items-center justify-center gap-x-6 gap-y-3 text-sm text-ink-soft',
            visible && 'is-visible',
          )}
        >
          <span className="inline-flex items-center gap-1.5">
            <CheckCircle2 className="h-4 w-4 text-safe" /> Privacy-minded checks
          </span>
          <span className="inline-flex items-center gap-1.5">
            <CheckCircle2 className="h-4 w-4 text-safe" /> No account required
          </span>
          <span className="inline-flex items-center gap-1.5">
            <CheckCircle2 className="h-4 w-4 text-safe" /> Calm, factual verdicts
          </span>
        </div>
      </div>
    </section>
  );
}
