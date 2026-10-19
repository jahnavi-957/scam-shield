import { cn } from '../../lib/utils';
import { useReveal } from '../../hooks/useReveal';
import { ShieldCheck, Eye, Users, Lock, Globe, Fingerprint } from 'lucide-react';
import { FeatureCard, StatCard } from '../../components/marketing/MarketingCards';

const features = [
  {
    icon: <ShieldCheck className="h-5 w-5" />,
    title: 'Instant classification',
    description: 'Messages and screenshots are analyzed in seconds, not minutes. Get a clear verdict before you reply.',
  },
  {
    icon: <Fingerprint className="h-5 w-5" />,
    title: 'Entity extraction',
    description: 'We pull out UPI IDs, phone numbers, URLs, and account details so you know exactly what you are dealing with.',
  },
  {
    icon: <Users className="h-5 w-5" />,
    title: 'Community-backed',
    description: 'Every report feeds a growing database. The more people check, the safer everyone becomes.',
  },
  {
    icon: <Eye className="h-5 w-5" />,
    title: 'Search before you pay',
    description: 'Look up any UPI ID, phone number, or URL to see its full report history before sending money.',
  },
  {
    icon: <Lock className="h-5 w-5" />,
    title: 'Private by design',
    description: 'Your messages are analyzed locally and never shared. No account, no tracking, no fuss.',
  },
  {
    icon: <Globe className="h-5 w-5" />,
    title: 'Calm, factual verdicts',
    description: 'No alarmism. We tell you what we found and why, in plain language, so you can decide with confidence.',
  },
];

const stats = [
  { value: '10,000+', label: 'messages analyzed' },
  { value: '24/7', label: 'always available' },
  { value: '<5s', label: 'average verdict time' },
  { value: '0', label: 'accounts required' },
];

export default function TrustSection() {
  const { ref, visible } = useReveal<HTMLDivElement>({ threshold: 0.12 });

  return (
    <section className="py-20 sm:py-28">
      <div className="container">
        <div ref={ref} className={cn('reveal max-w-2xl', visible && 'is-visible')}>
          <p className="text-meta">Why people trust Scam Shield</p>
          <h2 className="mt-3 text-headline">A check that respects your time.</h2>
          <p className="mt-4 text-body">
            Built for the moments that matter — a suspicious payment request, an
            urgent message, a screenshot you cannot quite read. We keep it fast,
            private, and calm.
          </p>
        </div>

        <div className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <div key={feature.title} ref={ref} className={cn('reveal', visible && 'is-visible')}>
              <FeatureCard icon={feature.icon} title={feature.title} description={feature.description} />
            </div>
          ))}
        </div>

        <div className="mt-16 grid grid-cols-2 gap-6 border-t border-line pt-10 sm:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.label} ref={ref} className={cn('reveal', visible && 'is-visible')}>
              <StatCard value={stat.value} label={stat.label} />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}