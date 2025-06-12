import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { KnowledgeBasePage } from './pages/KnowledgeBasePage';
import { SettingsPage } from './pages/SettingsPage';
import { MCPPage } from './pages/MCPPage';
import { MainLayout } from './components/layouts/MainLayout';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './contexts/ToastContext';
import { SettingsProvider, useSettings } from './contexts/SettingsContext';
import { ProjectPage } from './pages/ProjectPage';

const AppRoutes = () => {
  const { projectsEnabled } = useSettings();
  
  return (
    <Routes>
      <Route path="/" element={<KnowledgeBasePage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/mcp" element={<MCPPage />} />
      {projectsEnabled ? (
        <Route path="/projects" element={<ProjectPage />} />
      ) : (
        <Route path="/projects" element={<Navigate to="/" replace />} />
      )}
    </Routes>
  );
};

export function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <SettingsProvider>
          <Router>
            <MainLayout>
              <AppRoutes />
            </MainLayout>
          </Router>
        </SettingsProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}