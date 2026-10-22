import { create } from 'zustand';

// UI-only state — nothing here touches the server. Kept deliberately small:
// the current view, the payload awaiting analysis, and transient UI flags.
// Server data lives in React Query, not here.

export type View =
  | { kind: 'home' }
  | { kind: 'lookup' }
  | { kind: 'analyzing'; source: 'text' | 'screenshot' }
  | { kind: 'result'; analysis: AnalysisSummary }
  | { kind: 'entity'; value: string }
  | { kind: 'error'; message: string };

export interface AnalysisSummary {
  message_id: number;
  source: string;
  is_scam: boolean;
  scam_type: string;
  confidence: number;
  explanation: string;
  entities: { type: string; value: string; report_count: number }[];
  prior_reports: number;
  near_duplicates: number[];
  alert_triggered: boolean;
  created_at: string;
  truncated?: boolean;
  classifier_kind?: string;
  similarity_score?: number | null;
  matched_scam_id?: string | null;
}

interface UiState {
  view: View;
  pendingText: string;
  pendingFile: File | null;
  setView: (view: View) => void;
  syncPath: () => void;
  goHome: () => void;
  goLookup: () => void;
  goUpload: () => void;
  startTextAnalysis: (text: string) => void;
  startScreenshotAnalysis: (file: File) => void;
  showResult: (analysis: AnalysisSummary) => void;
  showError: (message: string) => void;
  goEntity: (value: string) => void;
  setPendingFile: (file: File | null) => void;
  reset: () => void;
}

const homeView: View = { kind: 'home' };

function viewForPath(pathname: string): View {
  if (pathname === '/lookup') return { kind: 'lookup' };
  if (pathname === '/upload') return { kind: 'analyzing', source: 'screenshot' };
  return homeView;
}

function currentPath(): string {
  return typeof window === 'undefined' ? '/' : window.location.pathname;
}

function navigate(pathname: string): void {
  if (typeof window !== 'undefined' && window.location.pathname !== pathname) {
    window.history.pushState({}, '', pathname);
  }
}

export const useUiStore = create<UiState>((set) => ({
  view: viewForPath(currentPath()),
  pendingText: '',
  pendingFile: null,

  setView: (view) => set({ view }),
  syncPath: () => set({ view: viewForPath(currentPath()) }),
  goHome: () => {
    navigate('/');
    set({ view: homeView, pendingText: '', pendingFile: null });
  },
  goLookup: () => {
    navigate('/lookup');
    set({ view: { kind: 'lookup' } });
  },
  goUpload: () => {
    navigate('/upload');
    set({ view: { kind: 'analyzing', source: 'screenshot' }, pendingFile: null });
  },
  startTextAnalysis: (text) =>
    set({ view: { kind: 'analyzing', source: 'text' }, pendingText: text }),
  startScreenshotAnalysis: (file) => {
    navigate('/upload');
    set({ view: { kind: 'analyzing', source: 'screenshot' }, pendingFile: file });
  },
  showResult: (analysis) => set({ view: { kind: 'result', analysis } }),
  showError: (message) => set({ view: { kind: 'error', message } }),
  goEntity: (value) => set({ view: { kind: 'entity', value } }),
  setPendingFile: (file) => set({ pendingFile: file }),
  reset: () => set({ view: homeView, pendingText: '', pendingFile: null }),
}));
