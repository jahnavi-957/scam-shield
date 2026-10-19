import { useUiStore } from '../store';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/LoadingState';
import { AlertTriangle } from 'lucide-react';

export default function ErrorPage() {
  const { view, goHome } = useUiStore();
  const message = view.kind === 'error' ? view.message : 'Something went wrong.';

  return (
    <div className="container flex min-h-[calc(100vh-3.5rem)] flex-col items-center justify-center py-24">
      <div className="w-full max-w-lg">
        <EmptyState
          icon={<AlertTriangle className="h-6 w-6" />}
          title="We hit a snag"
          description={message}
          action={
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button variant="primary" onClick={goHome}>
                Try again
              </Button>
            </div>
          }
        />
      </div>
    </div>
  );
}