import React, { useState, useEffect } from 'react';
import { Moon, Sun, FileText, Layout, Bot, Settings, Flame } from 'lucide-react';
import { Toggle } from '../ui/Toggle';
import { useTheme } from '../../contexts/ThemeContext';
import { credentialsService } from '../../services/credentialsService';
import { useToast } from '../../contexts/ToastContext';

export const FeaturesSection = () => {
  const {
    theme,
    setTheme
  } = useTheme();
  const { showToast } = useToast();
  const isDarkMode = theme === 'dark';
  const [projectsEnabled, setProjectsEnabled] = useState(true);
  
  // Commented out for future release
  const [agUILibraryEnabled, setAgUILibraryEnabled] = useState(false);
  const [agentsEnabled, setAgentsEnabled] = useState(false);
  
  const [logfireEnabled, setLogfireEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [projectsSchemaValid, setProjectsSchemaValid] = useState(true);
  const [projectsSchemaError, setProjectsSchemaError] = useState<string | null>(null);

  // Load settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      
      // Load both Logfire and Projects settings, plus check projects schema
      const [logfireResponse, projectsResponse, projectsHealthResponse] = await Promise.all([
        credentialsService.getCredential('LOGFIRE_ENABLED').catch(() => ({ value: undefined })),
        credentialsService.getCredential('PROJECTS_ENABLED').catch(() => ({ value: undefined })),
        fetch(`${credentialsService['baseUrl']}/api/projects/health`).catch(() => null)
      ]);
      
      // Set Logfire setting
      if (logfireResponse.value !== undefined) {
        setLogfireEnabled(logfireResponse.value === 'true');
      } else {
        setLogfireEnabled(false);
      }
      
      // Check projects schema health
      console.log('🔍 Projects health response:', {
        response: projectsHealthResponse,
        ok: projectsHealthResponse?.ok,
        status: projectsHealthResponse?.status,
        url: `${credentialsService['baseUrl']}/api/projects/health`
      });
      
      if (projectsHealthResponse && projectsHealthResponse.ok) {
        const healthData = await projectsHealthResponse.json();
        console.log('🔍 Projects health data:', healthData);
        
        const schemaValid = healthData.schema?.valid === true;
        setProjectsSchemaValid(schemaValid);
        
        if (!schemaValid) {
          setProjectsSchemaError(
            'Projects table not detected. Please ensure you have installed the archon_tasks.sql structure to your database and restart the server.'
          );
        } else {
          setProjectsSchemaError(null);
        }
      } else {
        // If health check fails, assume schema is invalid
        console.log('🔍 Projects health check failed');
        setProjectsSchemaValid(false);
        setProjectsSchemaError(
          'Unable to verify projects schema. Please ensure the backend is running and database is accessible.'
        );
      }
      
      // Set Projects setting (but only if schema is valid)
      if (projectsResponse.value !== undefined) {
        setProjectsEnabled(projectsResponse.value === 'true');
      } else {
        setProjectsEnabled(true); // Default to true
      }
      
    } catch (error) {
      console.error('Failed to load settings:', error);
      // Default values on error
      setLogfireEnabled(false);
      setProjectsEnabled(true);
      setProjectsSchemaValid(false);
      setProjectsSchemaError('Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handleProjectsToggle = async (checked: boolean) => {
    // Prevent duplicate calls while one is already in progress
    if (loading) return;
    
    try {
      setLoading(true);
      // Update local state immediately for responsive UI
      setProjectsEnabled(checked);

      // Save to backend
      await credentialsService.createCredential({
        key: 'PROJECTS_ENABLED',
        value: checked.toString(),
        is_encrypted: false,
        category: 'features',
        description: 'Enable or disable Projects and Tasks functionality'
      });

      showToast(
        checked ? 'Projects Enabled Successfully!' : 'Projects Now Disabled', 
        checked ? 'success' : 'warning'
      );
    } catch (error) {
      console.error('Failed to update projects setting:', error);
      // Revert local state on error
      setProjectsEnabled(!checked);
      showToast('Failed to update Projects setting', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleLogfireToggle = async (checked: boolean) => {
    // Prevent duplicate calls while one is already in progress
    if (loading) return;
    
    try {
      setLoading(true);
      // Update local state immediately for responsive UI
      setLogfireEnabled(checked);

      // Save to backend
      await credentialsService.createCredential({
        key: 'LOGFIRE_ENABLED',
        value: checked.toString(),
        is_encrypted: false,
        category: 'monitoring',
        description: 'Enable or disable Pydantic Logfire logging and observability'
      });

      showToast(
        checked ? 'Logfire Enabled Successfully!' : 'Logfire Now Disabled', 
        checked ? 'success' : 'warning'
      );
    } catch (error) {
      console.error('Failed to update logfire setting:', error);
      // Revert local state on error
      setLogfireEnabled(!checked);
      showToast('Failed to update Logfire setting', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleThemeToggle = (checked: boolean) => {
    setTheme(checked ? 'dark' : 'light');
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center mb-4">
        <Settings className="mr-2 text-blue-500" size={20} />
        <h2 className="text-xl font-semibold text-gray-800 dark:text-white">
          Features & Theme
        </h2>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-2">
        {/* Theme Toggle */}
        <div className="flex items-center gap-4 p-4 rounded-lg bg-gradient-to-r from-purple-500/5 to-purple-500/0">
          <div className="flex-1 min-w-0">
            <p className="font-medium text-gray-800 dark:text-white">
              Dark Mode
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Switch between light and dark themes
            </p>
          </div>
          <div className="flex-shrink-0">
            <Toggle checked={isDarkMode} onCheckedChange={handleThemeToggle} accentColor="purple" icon={isDarkMode ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />} />
          </div>
        </div>

        {/* Projects Toggle */}
        <div className="flex items-center gap-4 p-4 rounded-lg bg-gradient-to-r from-blue-500/5 to-blue-500/0">
          <div className="flex-1 min-w-0">
            <p className="font-medium text-gray-800 dark:text-white">
              Projects
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Enable Projects and Tasks functionality
            </p>
            {!projectsSchemaValid && projectsSchemaError && (
              <p className="text-xs text-red-500 dark:text-red-400 mt-1">
                ⚠️ {projectsSchemaError}
              </p>
            )}
          </div>
          <div className="flex-shrink-0">
            <Toggle 
              checked={projectsEnabled} 
              onCheckedChange={handleProjectsToggle} 
              accentColor="blue" 
              icon={<FileText className="w-5 h-5" />}
              disabled={loading || !projectsSchemaValid}
            />
          </div>
        </div>

        {/* COMMENTED OUT FOR FUTURE RELEASE - AG-UI Library Toggle */}
        {/*
        <div className="flex items-center gap-4 p-4 rounded-lg bg-gradient-to-r from-pink-500/5 to-pink-500/0">
          <div className="flex-1 min-w-0">
            <p className="font-medium text-gray-800 dark:text-white">
              AG-UI Library
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Enable component library functionality
            </p>
          </div>
          <div className="flex-shrink-0">
            <Toggle checked={agUILibraryEnabled} onCheckedChange={setAgUILibraryEnabled} accentColor="pink" icon={<Layout className="w-5 h-5" />} />
          </div>
        </div>
        */}

        {/* COMMENTED OUT FOR FUTURE RELEASE - Agents Toggle */}
        {/*
        <div className="flex items-center gap-4 p-4 rounded-lg bg-gradient-to-r from-green-500/5 to-green-500/0">
          <div className="flex-1 min-w-0">
            <p className="font-medium text-gray-800 dark:text-white">
              Agents
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Enable AI agents for automated tasks
            </p>
          </div>
          <div className="flex-shrink-0">
            <Toggle checked={agentsEnabled} onCheckedChange={setAgentsEnabled} accentColor="green" icon={<Bot className="w-5 h-5" />} />
          </div>
        </div>
        */}

        {/* Pydantic Logfire Toggle */}
        <div className="flex items-center gap-4 p-4 rounded-lg bg-gradient-to-r from-orange-500/5 to-orange-500/0">
          <div className="flex-1 min-w-0">
            <p className="font-medium text-gray-800 dark:text-white">
              Pydantic Logfire
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Structured logging and observability platform
            </p>
          </div>
          <div className="flex-shrink-0">
            <Toggle 
              checked={logfireEnabled} 
              onCheckedChange={handleLogfireToggle} 
              accentColor="orange" 
              icon={<Flame className="w-5 h-5" />}
              disabled={loading}
            />
          </div>
        </div>
      </div>
    </div>
  );
};