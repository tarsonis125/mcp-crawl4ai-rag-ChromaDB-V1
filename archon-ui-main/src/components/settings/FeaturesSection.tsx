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
  const [agUILibraryEnabled, setAgUILibraryEnabled] = useState(false);
  const [agentsEnabled, setAgentsEnabled] = useState(false);
  const [logfireEnabled, setLogfireEnabled] = useState(false);
  const [loading, setLoading] = useState(true);

  // Load settings on mount
  useEffect(() => {
    loadLogfireSettings();
  }, []);

  const loadLogfireSettings = async () => {
    try {
      setLoading(true);
      // Try to get the LOGFIRE_ENABLED setting from credentials
      const response = await credentialsService.getCredential('LOGFIRE_ENABLED');
      if (response.value !== undefined) {
        setLogfireEnabled(response.value === 'true');
      } else {
        // Default to false if not set
        setLogfireEnabled(false);
      }
    } catch (error) {
      console.error('Failed to load logfire settings:', error);
      // Default to false on error
      setLogfireEnabled(false);
    } finally {
      setLoading(false);
    }
  };

  const handleLogfireToggle = async (checked: boolean) => {
    try {
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
        `Logfire ${checked ? 'enabled' : 'disabled'} successfully!`, 
        'success'
      );
    } catch (error) {
      console.error('Failed to update logfire setting:', error);
      // Revert local state on error
      setLogfireEnabled(!checked);
      showToast('Failed to update Logfire setting', 'error');
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
          </div>
          <div className="flex-shrink-0">
            <Toggle checked={projectsEnabled} onCheckedChange={setProjectsEnabled} accentColor="blue" icon={<FileText className="w-5 h-5" />} />
          </div>
        </div>

        {/* AG-UI Library Toggle */}
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

        {/* Agents Toggle */}
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