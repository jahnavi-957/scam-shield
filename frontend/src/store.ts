import { create } from 'zustand';

// UI-only state — nothing here touches the server. Kept deliberately small:
// the current view, the payload awaiting analysis, and transient UI flags.
// Server data lives in React Query, not here.

export type View =
  | { kind: 'home' }
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
}

interface UiState {
  view: View;
  pendingText: string;
  pendingFile: File | null;
  setView: (view: View) => void;
  goHome: () => void;
  startTextAnalysis: (text: string) => void;
  startScreenshotAnalysis: (file: File) => void;
  showResult: (analysis: AnalysisSummary) => void;
  showError: (message: string) => void;
  goEntity: (value: string) => void;
  setPendingFile: (file: File | null) => void;
  reset: () => void;
}

const homeView: View = { kind: 'home' };

export const useUiStore = create<UiState>((set) => ({
  view: homeView,
  pendingText: '',
  pendingFile: null,

  setView: (view) => set({ view }),
  goHome: () => set({ view: homeView, pendingText: '', pendingFile: null }),
  startTextAnalysis: (text) =>
    set({ view: { kind: 'analyzing', source: 'text' }, pendingText: text }),
  startScreenshotAnalysis: (file) =>
    set({ view: { kind: 'analyzing', source: 'screenshot' }, pendingFile: file }),
  showResult: (analysis) => set({ view: { kind: 'result', analysis } }),
  showError: (message) => set({ view: { kind: 'error', message } }),
  goEntity: (value) => set({ view: { kind: 'entity', value } }),
  setPendingFile: (file) => set({ pendingFile: file }),
  reset: () => set({ view: homeView, pendingText: '', pendingFile: null }),
}));