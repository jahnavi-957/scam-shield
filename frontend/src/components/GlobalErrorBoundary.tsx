import { Component, ReactNode } from 'react';
import { Button } from './ui/Button';

interface GlobalErrorBoundaryProps {
  children: ReactNode;
}

interface GlobalErrorBoundaryState {
  hasError: boolean;
}

export class GlobalErrorBoundary extends Component<
  GlobalErrorBoundaryProps,
  GlobalErrorBoundaryState
> {
  state: GlobalErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): GlobalErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Uncaught frontend error', error, errorInfo);
  }

  handleRefresh = () => {
    window.location.reload();
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="flex min-h-screen items-center justify-center bg-bg px-6 py-16 text-center">
        <div className="w-full max-w-md rounded-2xl border border-line bg-bg-elevated p-8 shadow-sm">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-accent-soft text-accent">
            <span className="text-xl" aria-hidden="true">•</span>
          </div>
          <h1 className="mt-5 text-2xl font-semibold tracking-tight text-ink">
            Something went wrong
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-soft">
            The check could not be displayed. Refresh the page and try again.
          </p>
          <Button className="mt-6" onClick={this.handleRefresh}>
            Refresh page
          </Button>
        </div>
      </div>
    );
  }
}
