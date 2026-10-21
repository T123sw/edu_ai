import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';
export default defineConfig({
  base: './', plugins: [react()], cacheDir: '../.runtime/bubble-vite-cache',
  build: { outDir: '../.runtime/bubble-prototype-build', emptyOutDir: true, rollupOptions: { input: 'bubble-preview.html' } },
  server: { host: '127.0.0.1', port: 5250, strictPort: true, watch: null },
  preview: { host: '127.0.0.1', port: 5250, strictPort: true },
});
