import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { KnowledgeBasePage } from './pages/KnowledgeBasePage';
import { SettingsPage } from './pages/SettingsPage';
import { MCPPage } from './pages/MCPPage';
import { MainLayout } from './components/layouts/MainLayout';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './contexts/ToastContext';

export function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <Router>
          <MainLayout>
            <Routes>
              <Route path="/" element={<KnowledgeBasePage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/mcp" element={<MCPPage />} />
            </Routes>
          </MainLayout>
        </Router>
      </ToastProvider>
    </ThemeProvider>
  );
}