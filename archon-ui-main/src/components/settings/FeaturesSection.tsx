import React, { useState } from 'react';
import { Moon, Sun, FileText, Layout, Bot, Settings } from 'lucide-react';
import { Toggle } from '../ui/Toggle';
import { useTheme } from '../../contexts/ThemeContext';

export const FeaturesSection = () => {
  const {
    theme,
    setTheme
  } = useTheme();
  const isDarkMode = theme === 'dark';
  const [projectsEnabled, setProjectsEnabled] = useState(true);
  const [agUILibraryEnabled, setAgUILibraryEnabled] = useState(false);
  const [agentsEnabled, setAgentsEnabled] = useState(false);

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

      <div className="space-y-8">
        {/* Theme Toggle */}
        <div className="flex items-center justify-between p-4 rounded-lg bg-gradient-to-r from-purple-500/5 to-purple-500/0">
          <div className="flex items-center gap-4">
            <div className="p-2.5 rounded-md bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400">
              {isDarkMode ? <Moon className="w-6 h-6" /> : <Sun className="w-6 h-6" />}
            </div>
            <div>
              <p className="font-medium text-gray-800 dark:text-white">
                Dark Mode
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Switch between light and dark themes
              </p>
            </div>
          </div>
          <Toggle checked={isDarkMode} onCheckedChange={handleThemeToggle} accentColor="purple" icon={isDarkMode ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />} />
        </div>

        {/* Projects Toggle */}
        <div className="flex items-center justify-between p-4 rounded-lg bg-gradient-to-r from-blue-500/5 to-blue-500/0">
          <div className="flex items-center gap-4">
            <div className="p-2.5 rounded-md bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400">
              <FileText className="w-6 h-6" />
            </div>
            <div>
              <p className="font-medium text-gray-800 dark:text-white">
                Projects
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Enable Projects and Tasks functionality
              </p>
            </div>
          </div>
          <Toggle checked={projectsEnabled} onCheckedChange={setProjectsEnabled} accentColor="blue" icon={<FileText className="w-5 h-5" />} />
        </div>

        {/* AG-UI Library Toggle */}
        <div className="flex items-center justify-between p-4 rounded-lg bg-gradient-to-r from-pink-500/5 to-pink-500/0">
          <div className="flex items-center gap-4">
            <div className="p-2.5 rounded-md bg-pink-100 dark:bg-pink-900/30 text-pink-600 dark:text-pink-400">
              <Layout className="w-6 h-6" />
            </div>
            <div>
              <p className="font-medium text-gray-800 dark:text-white">
                AG-UI Library
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Enable component library functionality
              </p>
            </div>
          </div>
          <Toggle checked={agUILibraryEnabled} onCheckedChange={setAgUILibraryEnabled} accentColor="pink" icon={<Layout className="w-5 h-5" />} />
        </div>

        {/* Agents Toggle */}
        <div className="flex items-center justify-between p-4 rounded-lg bg-gradient-to-r from-green-500/5 to-green-500/0">
          <div className="flex items-center gap-4">
            <div className="p-2.5 rounded-md bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400">
              <Bot className="w-6 h-6" />
            </div>
            <div>
              <p className="font-medium text-gray-800 dark:text-white">
                Agents
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Enable AI agents for automated tasks
              </p>
            </div>
          </div>
          <Toggle checked={agentsEnabled} onCheckedChange={setAgentsEnabled} accentColor="green" icon={<Bot className="w-5 h-5" />} />
        </div>
      </div>
    </div>
  );
};