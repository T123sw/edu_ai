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

const enableFileWatching = process.env.EDU_AI_VITE_WATCH === '1';

// Vite watches the whole project root in development. Backend jobs update
// SQLite/WAL files and generated resources inside that root; without these
// exclusions every heartbeat can be interpreted as a page reload.
export const BACKEND_RUNTIME_WATCH_IGNORES = [
  '**/node_modules/**',
  '**/.git/**',
  '**/dist/**',
  '**/api/data/**',
  '**/api/course_data/**',
  '**/api/storage/**',
  '**/storage/**',
];

export default defineConfig({
  plugins: [react()],
  // This application imports every route from the root shell. Letting Vite
  // crawl that complete graph during startup pulls the renderer, Shiki,
  // ECharts, Ant Design icons, and thousands of modules into one blocking
  // optimization pass. Prebundle the known CommonJS boundaries and shared
  // UI entry points; transform the remaining ESM modules on demand.
  optimizeDeps: {
    noDiscovery: true,
    include: [
      'react',
      'react-dom',
      'react-dom/client',
      'react/jsx-runtime',
      'react/jsx-dev-runtime',
      // react-syntax-highlighter (loaded by the global job manager after
      // login) imports named symbols from this CommonJS package. Without
      // prebundling it, the browser receives the raw CJS entry and the
      // authenticated application crashes while resolving ForwardRef.
      'react-is',
      // Profile and settings reach Ant Design helpers that still publish a
      // CommonJS entry. Prebundle it so lazy route imports receive a real
      // default export instead of the raw module wrapper.
      'classnames',
      'zustand',
      'zustand/vanilla',
      // react-markdown reaches this CommonJS leaf through
      // hast-util-to-jsx-runtime. Convert the leaf once instead of eagerly
      // prebundling the entire markdown and syntax-language catalog.
      'style-to-js',
      'react-markdown',
      'remark-gfm',
      'remark-math',
      'rehype-katex',
      'react-syntax-highlighter/dist/esm/prism',
      'react-syntax-highlighter/dist/esm/styles/prism/vsc-dark-plus',
      // The AI workspace still contains legacy named imports from Ant
      // Design's package root. Prebundle that entry once so its CommonJS
      // leaves (dayjs plugins, copy-to-clipboard, and similar helpers) are
      // converted before any lazy route is opened.
      'antd',
      'antd/es/alert',
      'antd/es/button',
      'antd/es/card',
      'antd/es/checkbox',
      'antd/es/form',
      'antd/es/input',
      'antd/es/input-number',
      'antd/es/message',
      'antd/es/modal',
      'antd/es/segmented',
      'antd/es/skeleton',
      'antd/es/tag',
      'antd/es/typography',
      '@ant-design/icons/LockOutlined.js',
      '@ant-design/icons/UserOutlined.js',
    ],
  },
  resolve: {
    dedupe: ['react', 'react-dom', 'motion', 'echarts', 'shiki'],
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
      // The renderer's published bundle imports these optional peers from its
      // real file-linked path. Resolve them to the frontend's declared copies.
      'echarts/core': dep('echarts/core'),
      'echarts/charts': dep('echarts/charts'),
      'echarts/components': dep('echarts/components'),
      'echarts/renderers': dep('echarts/renderers'),
    },
  },
  server: {
    port: 5173,
    // The normal application launcher values stability over HMR. On Windows,
    // recursively watching this mixed frontend/backend repository (including
    // file-linked workspaces) can consume tens of thousands of handles and
    // starve HTTP responses. Developers can opt back into HMR with
    // EDU_AI_VITE_WATCH=1 when actively editing the frontend.
    watch: enableFileWatching
      ? { ignored: BACKEND_RUNTIME_WATCH_IGNORES }
      : null,
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


