import { QueryClient } from '@tanstack/react-query';

// Stale once per session — analysis results are immutable (they're stored
// rows with a message_id), so there is no benefit in refetching.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: Infinity,
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 1,
    },
  },
});

export const queryKeys = {
  health: ['health'] as const,
  entity: (value: string) => ['entity', value] as const,
};