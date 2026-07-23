import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './stitch/App';
import { AuthProvider } from './context/AuthContext';
import './stitch/styles.css';
// Optional CJK @font-face rules for imported PPTX slides; falls back silently
// to system fonts if the CDN (file.maic.chat) isn't reachable — see
// @openmaic/renderer's README "Fonts" section.
import '@openmaic/renderer/fonts.css';

const container = document.getElementById('root');

if (!container) {
  throw new Error("Root element '#root' was not found.");
}

createRoot(container).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>,
);
