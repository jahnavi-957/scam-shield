// Lightweight scroll-reveal hook. Uses IntersectionObserver to fade/slide
// elements into view as they enter the viewport. Respects
// prefers-reduced-motion by revealing immediately.
import { useEffect, useRef, useState } from 'react';

export function useReveal<T extends HTMLElement = HTMLElement>(options?: { threshold?: number; rootMargin?: string }) {
  const ref = useRef<T>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const prefersReduced =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (prefersReduced) {
      setVisible(true);
      return;
    }

    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: options?.threshold ?? 0.12, rootMargin: options?.rootMargin ?? '0px 0px -8% 0px' },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [options?.threshold, options?.rootMargin]);

  return { ref, visible };
}

// Re-exportable class string for the reveal animation.
export function revealClass(visible: boolean): string {
  return visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5 transition-all duration-700 ease-out';
}