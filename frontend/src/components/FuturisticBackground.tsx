import { useEffect, useRef } from 'react';

// Futuristic animated background: drifting grid + floating orbs + scanlines.
// Canvas-free and pure CSS so it stays lightweight on a demo machine.
export function FuturisticBackground() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    const move = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      el.style.setProperty('--mx', `${x * 20}px`);
      el.style.setProperty('--my', `${y * 20}px`);
    };
    const tick = () => {
      const t = performance.now() / 1000;
      el.style.setProperty('--t', `${Math.sin(t * 0.6) * 4}px`);
      raf = requestAnimationFrame(tick);
    };
    window.addEventListener('mousemove', move);
    raf = requestAnimationFrame(tick);
    return () => {
      window.removeEventListener('mousemove', move);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div
      ref={ref}
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
      aria-hidden="true"
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_35%,rgba(59,63,140,0.16),transparent_60%)]" />
      <div
        className="absolute inset-0 bg-[linear-gradient(rgba(59,63,140,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(59,63,140,0.08)_1px,transparent_1px)] bg-[size:48px_48px] [mask-image:radial-gradient(circle_at_var(--mx,_0)_var(--my,_0),black_30%,transparent_75%)]"
        style={{ maskPosition: '50% 40%' }}
      />
      <div className="absolute -left-24 top-1/4 h-72 w-72 rounded-full bg-accent/15 blur-3xl" />
      <div className="absolute -right-24 top-1/3 h-80 w-80 rounded-full bg-safe/10 blur-3xl" />
      <div className="absolute left-1/2 bottom-0 h-96 w-[40rem] -translate-x-1/2 rounded-full bg-accent/10 blur-3xl" />
      <div className="absolute inset-0 bg-[linear-gradient(transparent_0,rgba(0,0,0,0.4)_100%)]" />
    </div>
  );
}