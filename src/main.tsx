import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import './index.css';
import {isRunningInPiNet, onPiNetEvent} from './pinet-sdk';

// When running inside PiNet OS, forward bridge events as DOM
// CustomEvents so any React component can subscribe via
// window.addEventListener('pinet', ...).
// The listener is intentionally app-global and lives until page unload.
if (isRunningInPiNet()) {
  const cleanup = onPiNetEvent((event, data) => {
    window.dispatchEvent(new CustomEvent('pinet', {detail: {event, data}}));
  });
  window.addEventListener('unload', cleanup);
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
