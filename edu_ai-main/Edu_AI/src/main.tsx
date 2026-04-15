import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './stitch/App';
import { AuthProvider } from './context/AuthContext';
import './stitch/styles.css';

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
