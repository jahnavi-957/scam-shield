import { cn } from '../../lib/utils';
import { useReveal } from '../../hooks/useReveal';
import { TestimonialCard } from '../../components/marketing/MarketingCards';

const testimonials = [
  {
    quote: 'I almost sent money to a fake UPI ID. Scam Shield caught it in seconds. Saved me 40,000 rupees.',
    name: 'Arjun Mehta',
    company: 'Bangalore',
  },
  {
    quote: 'The explanation is calm and clear — no scare tactics, just the facts. I finally understood why that message was suspicious.',
    name: 'Priya Nair',
    company: 'Mumbai',
  },
  {
    quote: 'I screenshot a WhatsApp message and pasted it in. The tool read the text and flagged three known scam numbers. Incredible.',
    name: 'Rohan Das',
    company: 'Delhi',
  },
];

export default function SocialProofSection() {
  const { ref, visible } = useReveal<HTMLDivElement>({ threshold: 0.12 });

  return (
    <section className="py-20 sm:py-28">
      <div className="container">
        <div ref={ref} className={cn('reveal max-w-2xl text-center', visible && 'is-visible')}>
          <p className="text-meta">Real people, real checks</p>
          <h2 className="mt-3 text-headline">A calm check that catches real scams.</h2>
          <p className="mt-4 text-body">
            Scam Shield is used by people who want to verify a message before
            they act — not because they are paranoid, but because they are careful.
          </p>
        </div>

        <div className="mt-12 grid gap-6 sm:grid-cols-3">
          {testimonials.map((t) => (
            <div key={t.name} ref={ref} className={cn('reveal', visible && 'is-visible')}>
              <TestimonialCard quote={t.quote} name={t.name} company={t.company} />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}