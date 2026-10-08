import { useEffect, useState } from 'react';
import { fetchHealth, type HealthStatus } from './api';

type LoadState =
  | { phase: 'loading' }
  | { phase: 'ready'; health: HealthStatus }
  | { phase: 'error'; message: string };

export default function App() {
  const [state, setState] = useState<LoadState>({ phase: 'loading' });

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((health) => {
        if (!cancelled) setState({ phase: 'ready', health });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            phase: 'error',
            message: error instanceof Error ? error.message : String(error),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="container">
      <h1>Scam Shield</h1>
      <p className="subtitle">Local development status (M1 skeleton)</p>

      {state.phase === 'loading' && <p className="status">Checking backend…</p>}

      {state.phase === 'error' && (
        <div className="card error">
          <h2>Backend unreachable</h2>
          <p>{state.message}</p>
          <p className="hint">
            Make sure the stack is running: <code>docker compose up -d --build</code>
          </p>
        </div>
      )}

      {state.phase === 'ready' && (
        <div className="card">
          <h2>Backend online</h2>
          <ul className="status-list">
            <li>
              API status: <strong>{state.health.status}</strong>
            </li>
            <li>
              Service: <strong>{state.health.service}</strong>
            </li>
            <li>
              Database: <strong>{state.health.database}</strong>
            </li>
          </ul>
        </div>
      )}
    </main>
  );
}