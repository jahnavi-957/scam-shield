import HeroSection from './landing/HeroSection';
import TrustSection from './landing/TrustSection';
import SocialProofSection from './landing/SocialProofSection';
import FinalCta from './landing/FinalCta';

// The landing page is just its sections — App.tsx provides the shell.
export default function LandingPage() {
  return (
    <>
      <HeroSection />
      <TrustSection />
      <SocialProofSection />
      <FinalCta />
    </>
  );
}