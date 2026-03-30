import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.tsx';
import './index.css';
import {isRunningInPiNet, onPiNetEvent} from './pinet-sdk';

// When running inside PiNet OS, listen for bridge events and forward
// them as DOM CustomEvents so any component can subscribe.
if (isRunningInPiNet()) {
  onPiNetEvent((event, data) => {
    window.dispatchEvent(new CustomEvent('pinet', {detail: {event, data}}));
  });
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
