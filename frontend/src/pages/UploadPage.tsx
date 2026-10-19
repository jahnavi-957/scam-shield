import { useEffect, useRef, useState } from 'react';
import { Image, Upload } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { useUiStore } from '../store';
import { useAnalyzeScreenshot } from '../hooks/mutations';

const ACCEPTED = ['image/png', 'image/jpeg', 'image/jpg'];

export default function UploadPage() {
  const { goHome, showResult, showError } = useUiStore();
  const mutation = useAnalyzeScreenshot();

  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validate = (f: File): string | null => {
    if (!ACCEPTED.includes(f.type)) {
      return 'Please upload a PNG or JPG image.';
    }
    if (f.size > 10 * 1024 * 1024) {
      return 'File is too large. Keep it under 10 MB.';
    }
    return null;
  };

  const handleFile = (next: File | null) => {
    if (!next) {
      setFile(null);
      setError(null);
      return;
    }
    const msg = validate(next);
    if (msg) {
      setFile(null);
      setError(msg);
      return;
    }
    setError(null);
    setFile(next);
  };

  const handleSubmit = async () => {
    if (!file) return;
    try {
      const result = await mutation.mutateAsync(file);
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
      });
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Could not process the screenshot.');
    }
  };

  // Auto-trigger once a valid file is selected.
  useEffect(() => {
    if (file && !mutation.isPending) {
      handleSubmit();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file]);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFile(e.dataTransfer.files?.[0] ?? null);
  };

  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFile(e.target.files?.[0] ?? null);
  };

  const isBusy = mutation.isPending;

  return (
    <div className="container flex min-h-[calc(100vh-3.5rem)] flex-col items-center py-16 sm:py-24">
      <div className="w-full max-w-2xl">
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold tracking-tight text-ink sm:text-5xl">
            Check a screenshot before you act.
          </h1>
          <p className="mx-auto mt-3 max-w-lg text-base text-ink-soft">
            Drop a message screenshot onto the dropzone. We will extract the
            text and check it against known scam patterns.
          </p>
        </div>

        <Card padding="lg">
          <label
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={onDrop}
            className={[
              'flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 px-6 py-14 text-center transition-colors',
              isDragging
                ? 'border-accent bg-accent-soft'
                : 'border-dashed border-line bg-bg-soft/40 hover:bg-bg-soft',
              isBusy && 'cursor-wait opacity-60',
            ].join(' ')}
          >
            <span
              className="flex h-12 w-12 items-center justify-center rounded-full bg-bg-elevated text-ink-faint"
              aria-hidden="true"
            >
              <Image className="h-6 w-6" />
            </span>
            <p className="mt-4 text-base font-medium text-ink">
              {isBusy ? 'Uploading and reading…' : 'Drop a screenshot here'}
            </p>
            <p className="mt-1 text-sm text-ink-faint">
              PNG or JPG, up to 10 MB
            </p>
            <div className="mt-4 relative">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg"
                onChange={onPick}
                className="hidden"
                aria-label="Upload screenshot"
                disabled={isBusy}
              />
              <Button
                variant="secondary"
                size="md"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="h-4 w-4" /> Choose file
              </Button>
            </div>
          </label>

          {error && (
            <p className="mt-3 text-sm text-danger" role="alert">
              {error}
            </p>
          )}
        </Card>

        <div className="mt-5 flex justify-center">
          <Button variant="ghost" onClick={goHome} disabled={isBusy}>
            Analyze text instead
          </Button>
        </div>
      </div>
    </div>
  );
}