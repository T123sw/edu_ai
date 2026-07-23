import path from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';

// @openmaic/dsl and @openmaic/renderer are npm `file:` deps pointing into
// openmaic-sidecar/packages/@openmaic/* (see docs/spec/patches/002). npm
// creates a symlink there, and that sidecar checkout has its own
// node_modules/react (v19) and node_modules/motion (v12) for its own
// Next.js app. `resolve.dedupe` alone wasn't enough to stop Vite resolving
// those bare specifiers relative to the symlink's real path — explicit
// aliases force every `react`/`motion` import in the module graph to this
// project's own copies, regardless of which package does the importing.
// Without this, renderer's motion/react usage (AnimatePresence in
// SpotlightOverlay etc.) loads a second React instance and crashes with
// "Invalid hook call".
function dep(name: string) {
  return path.resolve(process.cwd(), 'node_modules', name);
}

export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ['react', 'react-dom', 'motion'],
    alias: {
      // Aliases match exact bare specifiers only (no prefix matching), so
      // every subpath actually imported anywhere in the dependency tree
      // needs its own entry.
      'react-dom/client': dep('react-dom/client'),
      'react-dom': dep('react-dom'),
      'react/jsx-dev-runtime': dep('react/jsx-dev-runtime'),
      'react/jsx-runtime': dep('react/jsx-runtime'),
      react: dep('react'),
      'motion/react': dep('motion/react'),
      motion: dep('motion'),
    },
  },
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


