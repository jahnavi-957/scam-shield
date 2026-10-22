import { useEffect, useState } from 'react';

// Full-screen loading/entrance animation. Plays once on mount, then
// fades out to reveal the app. Designed to feel like a product boot-up,
// not a spinner on a blank page.
export function LoadingScreen({ onDone }: { onDone: () => void }) {
  const [phase, setPhase] = useState<'boot' | 'reveal' | 'done'>('boot');

  useEffect(() => {
    const t1 = setTimeout(() => setPhase('reveal'), 900);
    const t2 = setTimeout(() => {
      setPhase('done');
      onDone();
    }, 1900);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [onDone]);

  if (phase === 'done') return null;

  return (
    <div
      className={
        'fixed inset-0 z-[9999] flex min-h-screen w-full flex-col items-center justify-center overflow-hidden bg-bg text-ink transition-opacity duration-700' +
        (phase === 'reveal' ? ' opacity-0' : ' opacity-100')
      }
    >
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_40%,rgba(59,63,140,0.18),transparent_60%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(rgba(59,63,140,0.06)_1px,transparent_1px),linear-gradient(90deg,rgba(59,63,140,0.06)_1px,transparent_1px)] bg-[size:44px_44px] [mask-image:radial-gradient(circle_at_50%_45%,black_30%,transparent_75%)]" />
      </div>

      <div className="relative">
        <div className="absolute inset-0 blur-2xl">
          <div className="h-16 w-16 animate-pulse-soft rounded-2xl bg-accent/40" />
        </div>
        <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-accent-soft text-accent shadow-md">
          <ShieldIcon />
        </div>
      </div>

      <p className="mt-6 text-sm font-medium tracking-[0.2em] text-ink-faint uppercase">
        {phase === 'boot' ? 'Initializing' : 'Ready'}
      </p>

      <div className="mt-3 flex items-center gap-1.5">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className="h-1.5 w-1.5 rounded-full bg-accent"
            style={{
              animation: `bootDot 1.2s ${i * 0.12}s ease-in-out infinite`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

function ShieldIcon() {
  return (
    <svg className="h-8 w-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}