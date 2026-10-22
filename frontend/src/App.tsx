import { useEffect, useState } from 'react';
import { FuturisticBackground } from './components/FuturisticBackground';
import { LoadingScreen } from './components/LoadingScreen';
import { AppShell } from './components/layout/AppShell';
import { Header } from './components/layout/Header';
import { Footer } from './components/layout/Footer';
import { useUiStore } from './store';
import LandingPage from './pages/LandingPage';
import UploadPage from './pages/UploadPage';
import ResultPage from './pages/ResultPage';
import ErrorPage from './pages/ErrorPage';
import LookupPage from './pages/LookupPage';

export default function App() {
  const [booted, setBooted] = useState(false);
  const { view, syncPath } = useUiStore();

  useEffect(() => {
    window.addEventListener('popstate', syncPath);
    return () => window.removeEventListener('popstate', syncPath);
  }, [syncPath]);

  return (
    <>
      <FuturisticBackground />
      {!booted && <LoadingScreen onDone={() => setBooted(true)} />}
      <div className={booted ? 'opacity-100' : 'opacity-0 transition-opacity duration-700'}>
        <AppShell>
          <Header />
          <main id="main" className="flex-1">
            {view.kind === 'home' ? (
              <LandingPage />
            ) : view.kind === 'analyzing' && view.source === 'screenshot' ? (
              <UploadPage />
            ) : view.kind === 'analyzing' && view.source === 'text' ? (
              <AnalyzingTextInline />
            ) : view.kind === 'result' ? (
              <ResultPage />
            ) : view.kind === 'error' ? (
              <ErrorPage />
            ) : view.kind === 'lookup' || view.kind === 'entity' ? (
              <LookupPage />
            ) : null}
          </main>
          <Footer />
        </AppShell>
      </div>
    </>
  );
}

function AnalyzingTextInline() {
  return (
    <div className="container flex min-h-[calc(100vh-3.5rem)] flex-col items-center justify-center py-24 text-center">
      <div className="h-10 w-10 animate-pulse-soft rounded-full bg-accent/20" aria-hidden="true" />
      <h2 className="mt-6 text-2xl font-semibold tracking-tight text-ink">Analyzing your message</h2>
      <p className="mt-2 max-w-sm text-base text-ink-faint">Classifying the message and flagging any known entities.</p>
    </div>
  );
}
