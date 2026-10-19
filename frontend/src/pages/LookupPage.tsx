import { useState } from 'react';
import { useUiStore } from '../store';
import { useEntityHistory } from '../hooks/mutations';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Card } from '../components/ui/Card';
import { EmptyState, LoadingState } from '../components/ui/LoadingState';
import { Badge } from '../components/ui/StatusIndicator';
import { EntityListItem } from '../components/ui/EntityListItem';
import { Link2, Phone, ShieldCheck, User, AlertTriangle, Search } from 'lucide-react';

export default function LookupPage() {
  const { view, goEntity, goHome } = useUiStore();
  const [input, setInput] = useState(view.kind === 'entity' ? view.value : '');
  const value = view.kind === 'entity' ? view.value : '';

  const query = useEntityHistory(value, view.kind === 'entity');
  const isSearching = view.kind === 'entity' && query.isPending;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;
    goEntity(trimmed);
  };

  return (
    <div className="container py-12 sm:py-16">
      <div className="mx-auto max-w-2xl">
        <div className="mb-6">
          <Button variant="ghost" size="sm" onClick={goHome}>
            ← Home
          </Button>
        </div>

        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold tracking-tight text-ink sm:text-5xl">
            Search before you pay.
          </h1>
          <p className="mx-auto mt-3 max-w-lg text-base text-ink-soft">
            Look up a UPI ID, phone number, or URL to see how many times it
            has been reported as a scam.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. fraud123@okaxis, +91 98765 43210, https://t.me/scam"
            aria-label="Entity to look up"
          />
          <Button type="submit" size="lg" className="shrink-0">
            <Search className="h-4 w-4" /> Lookup
          </Button>
        </form>

        <div className="mt-8">
          {!value && (
            <EmptyState
              icon={<Search className="h-6 w-6" />}
              title="No search yet"
              description="Enter a UPI ID, phone number, or URL above to see its report history."
            />
          )}

          {value && isSearching && <LoadingState label="Checking reports" />}

          {value && !isSearching && query.isError && (
            <EmptyState
              icon={<ShieldCheck className="h-6 w-6" />}
              title="No reports found"
              description={query.error.message}
            />
          )}

          {value && !isSearching && query.data && (
            <div className="space-y-6">
              <Card padding="lg">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-soft text-accent" aria-hidden="true">
                      {entityIcon(query.data.entity_type)}
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">
                        {query.data.entity_type}
                      </p>
                      <p className="truncate text-base font-semibold text-ink" title={query.data.value}>
                        {query.data.value}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold tracking-tight text-ink">
                      {query.data.report_count}
                    </p>
                    <p className="text-xs text-ink-faint">
                      report{query.data.report_count === 1 ? '' : 's'}
                    </p>
                  </div>
                </div>
              </Card>

              {query.data.report_count > 0 ? (
                <div>
                  <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-faint">
                    Recent reports
                  </h2>
                  <ul className="space-y-2">
                    {query.data.recent_reports.map((report) => (
                      <li key={report.message_id}>
                        <EntityListItem
                          icon={report.is_scam ? <AlertTriangle className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
                          label={report.source}
                          value={report.scam_type ?? 'No verdict'}
                          meta={
                            <div className="flex flex-col text-right">
                              <Badge tone={report.is_scam ? 'danger' : 'safe'}>
                                {report.is_scam ? 'Scam' : 'Safe'}
                              </Badge>
                              <span className="mt-1 text-xs text-ink-faint">
                                {formatDate(report.created_at)}
                              </span>
                            </div>
                          }
                        />
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <Card padding="lg">
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 items-center justify-center rounded-full bg-safe-soft text-safe" aria-hidden="true">
                      <ShieldCheck className="h-5 w-5" />
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-ink">
                        No scam reports on record
                      </p>
                      <p className="text-sm text-ink-faint">
                        This entity has not been flagged by the community yet.
                      </p>
                    </div>
                  </div>
                </Card>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function entityIcon(type: string) {
  const t = type.toLowerCase();
  if (t.includes('upi') || t.includes('email')) return <Link2 className="h-5 w-5" />;
  if (t.includes('phone') || t.includes('mobile')) return <Phone className="h-5 w-5" />;
  if (t.includes('url') || t.includes('link')) return <Link2 className="h-5 w-5" />;
  return <User className="h-5 w-5" />;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}