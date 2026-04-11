import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/ppt': {
        target: 'http://127.0.0.1:46080',
        changeOrigin: true,
      },
      '/assets/HEU': {
        target: 'http://127.0.0.1:46080',
        changeOrigin: true,
      },
      '/assets/test': {
        target: 'http://127.0.0.1:46080',
        changeOrigin: true,
      },
    },
  },
});


