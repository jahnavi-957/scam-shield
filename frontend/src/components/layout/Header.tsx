import { Upload } from 'lucide-react';
import { useUiStore } from '../../store';

export function Header() {
  const { goHome, goLookup, goUpload } = useUiStore();

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-bg/85 backdrop-blur">
      <div className="container flex h-14 items-center justify-between">
        <a
          href="/"
          onClick={(event) => {
            event.preventDefault();
            goHome();
          }}
          className="flex items-center gap-2 text-base font-semibold tracking-tight text-ink"
          aria-label="Scam Shield home"
        >
          <Wordmark />
        </a>

        <nav className="flex items-center gap-1" aria-label="Primary">
          <a
            href="/"
            onClick={(event) => {
              event.preventDefault();
              goHome();
            }}
            className="rounded-md px-3 py-1.5 text-sm font-medium text-ink-soft transition-colors hover:bg-bg-soft hover:text-ink"
          >
            Analyze
          </a>
          <a
            href="/lookup"
            onClick={(event) => {
              event.preventDefault();
              goLookup();
            }}
            className="rounded-md px-3 py-1.5 text-sm font-medium text-ink-soft transition-colors hover:bg-bg-soft hover:text-ink"
          >
            Lookup
          </a>
          <a
            href="/upload"
            onClick={(event) => {
              event.preventDefault();
              goUpload();
            }}
            className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-ink-soft transition-colors hover:bg-bg-soft hover:text-ink"
          >
            <Upload className="h-3.5 w-3.5" /> Screenshot
          </a>
        </nav>
      </div>
    </header>
  );
}

function Wordmark() {
  return (
    <span className="flex items-center gap-2">
      <span
        className="flex h-7 w-7 items-center justify-center rounded-md bg-accent/10 text-accent"
        aria-hidden="true"
      >
        <ShieldCheck />
      </span>
      <span className="tracking-tight">Scam&nbsp;Shield</span>
    </span>
  );
}

function ShieldCheck() {
  return (
    <svg
      className="h-4 w-4"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}
