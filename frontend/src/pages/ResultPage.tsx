import { useUiStore } from '../store';
import { Button } from '../components/ui/Button';
import { StatusIndicator, Badge } from '../components/ui/StatusIndicator';
import { EntityListItem } from '../components/ui/EntityListItem';
import { EmptyState } from '../components/ui/LoadingState';
import {
  Clock,
  Link2,
  Phone,
  ShieldCheck,
  User,
  AlertTriangle,
} from 'lucide-react';

export default function ResultPage() {
  const { view, goHome } = useUiStore();

  if (view.kind !== 'result') {
    return null;
  }

  const { analysis } = view;
  const isScam = analysis.is_scam;
  const tone: 'danger' | 'safe' = isScam ? 'danger' : 'safe';
  const verdict = isScam ? `This is a ${analysis.scam_type}` : 'This looks safe';

  const confidenceLabel = confidenceWord(analysis.confidence);

  return (
    <div className="container py-12 sm:py-16">
      <div className="mx-auto max-w-2xl">
        <div className="mb-6">
          <Button variant="ghost" size="sm" onClick={goHome}>
            ← Analyze another message
          </Button>
        </div>

        <div className="rounded-2xl border border-line bg-bg-elevated p-7 shadow-sm sm:p-9">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
            <span
              className={[
                'flex h-14 w-14 shrink-0 items-center justify-center rounded-full',
                isScam ? 'bg-danger-soft text-danger' : 'bg-safe-soft text-safe',
              ].join(' ')}
              aria-hidden="true"
            >
              {isScam ? (
                <AlertTriangle className="h-7 w-7" />
              ) : (
                <ShieldCheck className="h-7 w-7" />
              )}
            </span>
            <div className="flex-1">
              <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">
                Verdict
              </p>
              <h1 className="mt-1 text-3xl font-bold tracking-tight text-ink sm:text-4xl">
                {verdict}
              </h1>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <StatusIndicator
                  tone={tone}
                  label={isScam ? 'Scam detected' : 'Looks safe'}
                  description={confidenceLabel}
                />
                <Badge tone={tone}>
                  {Math.round(analysis.confidence * 100)}% confidence
                </Badge>
              </div>
            </div>
          </div>

          <div className="mt-7 border-t border-line pt-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-faint">
              Why we think so
            </h2>
            <p className="mt-2 text-base leading-relaxed text-ink-soft">
              {analysis.explanation}
            </p>
          </div>

          <div className="mt-7 border-t border-line pt-6">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-faint">
                Entities found
              </h2>
              <span className="text-xs text-ink-faint">
                {analysis.entities.length}{' '}
                {analysis.entities.length === 1 ? 'item' : 'items'}
              </span>
            </div>

            {analysis.entities.length === 0 ? (
              <EmptyState
                icon={<ShieldCheck className="h-6 w-6" />}
                title="No entities identified"
                description="No UPI IDs, phone numbers, or URLs were found in this message."
                className="mt-4"
              />
            ) : (
              <ul className="mt-4 space-y-2">
                {analysis.entities.map((entity, i) => (
                  <li key={`${entity.type}-${entity.value}-${i}`}>
                    <EntityListItem
                      icon={entityIcon(entity.type)}
                      label={entity.type}
                      value={entity.value}
                      meta={
                        <Badge tone="neutral">
                          {entity.report_count}{' '}
                          report{entity.report_count === 1 ? '' : 's'}
                        </Badge>
                      }
                    />
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="mt-7 border-t border-line pt-6">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-ink-soft">
              <span className="inline-flex items-center gap-1.5">
                <Clock className="h-4 w-4 text-ink-faint" />
                Reported {analysis.prior_reports}{' '}
                time{analysis.prior_reports === 1 ? '' : 's'} before
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Link2 className="h-4 w-4 text-ink-faint" />
                Source: {analysis.source}
              </span>
            </div>
          </div>

          {analysis.near_duplicates.length > 0 && (
            <div className="mt-7 border-t border-line pt-6">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-faint">
                Similar reports
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-ink-soft">
                This message is similar to reports already in Scam Shield.
              </p>
              <ul className="mt-4 grid gap-2 sm:grid-cols-2">
                {analysis.near_duplicates.map((messageId, index) => (
                  <li
                    key={`${messageId}-${index}`}
                    className="rounded-lg border border-line bg-bg-soft px-4 py-3 text-sm text-ink"
                  >
                    Report <span className="font-semibold">#{messageId}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="mt-6 flex justify-center">
          <Button variant="primary" size="lg" onClick={goHome}>
            Analyze another message
          </Button>
        </div>
      </div>
    </div>
  );
}

function entityIcon(type: string) {
  const t = type.toLowerCase();
  if (t.includes('upi') || t.includes('email')) return <Link2 className="h-4 w-4" />;
  if (t.includes('phone') || t.includes('mobile') || t.includes('number')) return <Phone className="h-4 w-4" />;
  if (t.includes('url') || t.includes('link') || t.includes('website')) return <Link2 className="h-4 w-4" />;
  if (t.includes('name') || t.includes('person')) return <User className="h-4 w-4" />;
  return <ShieldCheck className="h-4 w-4" />;
}

function confidenceWord(confidence: number): string {
  if (confidence >= 0.85) return 'High confidence';
  if (confidence >= 0.6) return 'Moderate confidence';
  if (confidence >= 0.4) return 'Low confidence';
  return 'Uncertain — review manually';
}
