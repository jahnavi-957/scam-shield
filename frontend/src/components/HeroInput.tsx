import { useEffect, useRef, useState } from 'react';
import { Textarea } from '../components/ui/Textarea';
import { Button } from '../components/ui/Button';
import { useUiStore } from '../store';
import { useAnalyzeText } from '../hooks/mutations';
import { useReveal, revealClass } from '../hooks/useReveal';

export default function HeroInput() {
  const { goHome, showResult, showError } = useUiStore();
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
    <div ref={ref} className={revealClass(visible)}>
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
          <Button variant="primary" size="lg" onClick={handleSubmit} disabled={isBusy}>
            {isBusy ? 'Analyzing…' : 'Analyze'}
          </Button>
        </div>
      </div>
    </div>
  );
}
