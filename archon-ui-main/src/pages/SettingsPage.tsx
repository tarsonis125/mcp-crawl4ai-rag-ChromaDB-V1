import React, { useState } from 'react';
import { Save, Key, Globe, Database, Sun, Moon } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Button } from '../components/ui/Button';
import { ThemeToggle } from '../components/ui/ThemeToggle';
import { useTheme } from '../contexts/ThemeContext';
import { useStaggeredEntrance } from '../hooks/useStaggeredEntrance';
export const SettingsPage = () => {
  const [openAIKey, setOpenAIKey] = useState('');
  const [anthropicKey, setAnthropicKey] = useState('');
  const [mistralKey, setMistralKey] = useState('');
  const [environment, setEnvironment] = useState('production');
  const [debugMode, setDebugMode] = useState(false);
  const [maxTokens, setMaxTokens] = useState(4096);
  const {
    theme
  } = useTheme();
  // Use staggered entrance animation
  const {
    isVisible,
    containerVariants,
    itemVariants,
    titleVariants
  } = useStaggeredEntrance([1, 2, 3, 4],
  // Updated to include the new appearance section
  0.15);
  return <motion.div initial="hidden" animate={isVisible ? 'visible' : 'hidden'} variants={containerVariants}>
      <motion.h1 className="text-3xl font-bold text-gray-800 dark:text-white mb-8" variants={titleVariants}>
        Settings
      </motion.h1>
      {/* Appearance Settings */}
      <motion.div className="mb-8" variants={itemVariants}>
        <h2 className="text-xl font-semibold text-gray-800 dark:text-white mb-4 flex items-center">
          <Sun className="mr-2 text-blue-500" size={20} />
          Appearance
        </h2>
        <Card accentColor="blue" className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-gray-800 dark:text-white font-medium">
                Theme Mode
              </h3>
              <p className="text-gray-600 dark:text-zinc-400 text-sm">
                Switch between dark and light mode
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-gray-600 dark:text-zinc-400 text-sm">
                {theme === 'dark' ? 'Dark' : 'Light'} Mode
              </span>
              <ThemeToggle accentColor="blue" />
            </div>
          </div>
        </Card>
      </motion.div>
      {/* API Keys Section */}
      <motion.div className="mb-8" variants={itemVariants}>
        <h2 className="text-xl font-semibold text-gray-800 dark:text-white mb-4 flex items-center">
          <Key className="mr-2 text-pink-500" size={20} />
          API Keys
        </h2>
        <Card accentColor="pink" className="space-y-4">
          <Input label="OpenAI API Key" type="password" value={openAIKey} onChange={e => setOpenAIKey(e.target.value)} placeholder="sk-..." accentColor="pink" />
          <Input label="Anthropic API Key" type="password" value={anthropicKey} onChange={e => setAnthropicKey(e.target.value)} placeholder="sk-ant-..." accentColor="pink" />
          <Input label="Mistral API Key" type="password" value={mistralKey} onChange={e => setMistralKey(e.target.value)} placeholder="..." accentColor="pink" />
        </Card>
      </motion.div>
      {/* Environment Settings */}
      <motion.div className="mb-8" variants={itemVariants}>
        <h2 className="text-xl font-semibold text-gray-800 dark:text-white mb-4 flex items-center">
          <Globe className="mr-2 text-green-500" size={20} />
          Environment Settings
        </h2>
        <Card accentColor="green" className="space-y-4">
          <Select label="Environment" value={environment} onChange={e => setEnvironment(e.target.value)} options={[{
          value: 'development',
          label: 'Development'
        }, {
          value: 'staging',
          label: 'Staging'
        }, {
          value: 'production',
          label: 'Production'
        }]} accentColor="green" />
          <div className="flex items-center">
            <input type="checkbox" id="debugMode" checked={debugMode} onChange={e => setDebugMode(e.target.checked)} className="mr-2 h-4 w-4 rounded border-zinc-700 bg-black dark:bg-black text-green-500 focus:ring-0 focus:ring-offset-0" />
            <label htmlFor="debugMode" className="text-gray-700 dark:text-zinc-300">
              Enable Debug Mode
            </label>
          </div>
          <Input label="Max Tokens" type="number" value={maxTokens.toString()} onChange={e => setMaxTokens(parseInt(e.target.value))} min={1} max={16384} accentColor="green" />
        </Card>
      </motion.div>
      {/* Save Button */}
      <motion.div variants={itemVariants}>
        <Button variant="primary" accentColor="green" className="shadow-lg shadow-emerald-500/20">
          <Save className="w-4 h-4 mr-2 inline" />
          <span>Save Settings</span>
        </Button>
      </motion.div>
    </motion.div>;
};