import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App, { AuthProvider } from './App.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>,
);