import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  cacheDir: '/tmp/.vite_cache',
  server: {
    // Expose to 0.0.0.0 so the Vite container is reachable from the host browser.
    host: true,
    port: 5173,
  },
});