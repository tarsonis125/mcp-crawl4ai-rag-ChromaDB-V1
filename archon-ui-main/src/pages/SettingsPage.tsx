import React, { useState, useEffect } from 'react';
import { Save, Key, Settings, Database, Sun, Plus, Trash2, Loader } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Button } from '../components/ui/Button';
import { ThemeToggle } from '../components/ui/ThemeToggle';
import { useTheme } from '../contexts/ThemeContext';
import { useToast } from '../contexts/ToastContext';
import { useStaggeredEntrance } from '../hooks/useStaggeredEntrance';
import { credentialsService, Credential, RagSettings } from '../services/credentialsService';

interface CustomCredential {
  key: string;
  value: string;
  description: string;
}

export const SettingsPage = () => {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [ragSettings, setRagSettings] = useState<RagSettings>({
    USE_CONTEXTUAL_EMBEDDINGS: false,
    USE_HYBRID_SEARCH: false,
    USE_AGENTIC_RAG: false,
    USE_RERANKING: false,
    MODEL_CHOICE: 'gpt-4o-mini'
  });
  const [customCredentials, setCustomCredentials] = useState<CustomCredential[]>([]);
  const [newCredential, setNewCredential] = useState<CustomCredential>({ key: '', value: '', description: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { theme } = useTheme();
  const { showToast } = useToast();
  
  // Use staggered entrance animation
  const { isVisible, containerVariants, itemVariants, titleVariants } = useStaggeredEntrance(
    [1, 2, 3, 4],
    0.15
  );

  // Load credentials and settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Load all credentials
      const allCredentials = await credentialsService.getAllCredentials();
      setCredentials(allCredentials);
      
      // Separate custom credentials (non-system ones)
      const customCreds = allCredentials
        .filter(cred => cred.category === 'api_keys' || cred.category === 'custom')
        .map(cred => ({
          key: cred.key,
          value: cred.value || cred.encrypted_value ? '' : '', // Don't show encrypted values
          description: cred.description || ''
        }));
      setCustomCredentials(customCreds);
      
      // Load RAG settings
      const settings = await credentialsService.getRagSettings();
      setRagSettings(settings);
    } catch (err) {
      setError('Failed to load settings');
      console.error(err);
      showToast('Failed to load settings', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSettings = async () => {
    try {
      setSaving(true);
      setError(null);
      
      // Save RAG settings
      await credentialsService.updateRagSettings(ragSettings);
      
      // Save custom credentials
      const promises = customCredentials.map(cred => 
        credentialsService.updateCredential({
          key: cred.key,
          value: cred.value,
          description: cred.description,
          is_encrypted: cred.key.toLowerCase().includes('key') || cred.key.toLowerCase().includes('secret'),
          category: 'api_keys'
        })
      );
      
      await Promise.all(promises);
      
      // Reload settings to confirm
      await loadSettings();
      
      // Show success toast
      showToast('Settings saved successfully!', 'success');
    } catch (err) {
      setError('Failed to save settings');
      console.error(err);
      showToast('Failed to save settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleAddCredential = async () => {
    if (!newCredential.key) return;
    
    try {
      await credentialsService.createCredential({
        key: newCredential.key,
        value: newCredential.value,
        description: newCredential.description,
        is_encrypted: newCredential.key.toLowerCase().includes('key') || newCredential.key.toLowerCase().includes('secret'),
        category: 'api_keys'
      });
      
      setCustomCredentials([...customCredentials, newCredential]);
      setNewCredential({ key: '', value: '', description: '' });
      showToast(`Credential ${newCredential.key} added successfully!`, 'success');
    } catch (err) {
      setError('Failed to add credential');
      console.error(err);
      showToast('Failed to add credential', 'error');
    }
  };

  const handleDeleteCredential = async (key: string) => {
    try {
      await credentialsService.deleteCredential(key);
      setCustomCredentials(customCredentials.filter(cred => cred.key !== key));
      showToast(`Credential ${key} deleted successfully!`, 'success');
    } catch (err) {
      setError('Failed to delete credential');
      console.error(err);
      showToast('Failed to delete credential', 'error');
    }
  };

  const updateCredentialValue = (key: string, value: string) => {
    setCustomCredentials(customCredentials.map(cred => 
      cred.key === key ? { ...cred, value } : cred
    ));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader className="animate-spin text-gray-500" size={32} />
      </div>
    );
  }

  return (
    <motion.div
      initial="hidden"
      animate={isVisible ? 'visible' : 'hidden'}
      variants={containerVariants}
    >
      <motion.h1
        className="text-3xl font-bold text-gray-800 dark:text-white mb-8"
        variants={titleVariants}
      >
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

      {/* Credentials Section */}
      <motion.div className="mb-8" variants={itemVariants}>
        <h2 className="text-xl font-semibold text-gray-800 dark:text-white mb-4 flex items-center">
          <Key className="mr-2 text-pink-500" size={20} />
          Credentials
        </h2>
        <Card accentColor="pink" className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-zinc-400 mb-4">
            Manage API keys and other credentials. Required credentials include OpenAI API key for embeddings.
          </p>
          
          {/* Standard Credentials */}
          <div className="space-y-4">
            {customCredentials.map((cred) => (
              <div key={cred.key} className="flex items-center gap-3">
                <div className="flex-1">
                  <Input
                    label={cred.key}
                    type={cred.key.toLowerCase().includes('key') ? 'password' : 'text'}
                    value={cred.value}
                    onChange={(e) => updateCredentialValue(cred.key, e.target.value)}
                    placeholder={cred.description || `Enter ${cred.key}`}
                    accentColor="pink"
                  />
                </div>
                <Button
                  variant="secondary"
                  onClick={() => handleDeleteCredential(cred.key)}
                  className="mt-6"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}
          </div>

          {/* Add New Credential */}
          <div className="border-t border-gray-200 dark:border-zinc-700 pt-4">
            <h4 className="text-sm font-medium text-gray-700 dark:text-zinc-300 mb-3">
              Add Custom Credential
            </h4>
            <div className="space-y-3">
              <Input
                label="Key Name"
                value={newCredential.key}
                onChange={(e) => setNewCredential({ ...newCredential, key: e.target.value })}
                placeholder="e.g., ANTHROPIC_API_KEY"
                accentColor="pink"
              />
              <Input
                label="Value"
                type="password"
                value={newCredential.value}
                onChange={(e) => setNewCredential({ ...newCredential, value: e.target.value })}
                placeholder="Enter value"
                accentColor="pink"
              />
              <Input
                label="Description (optional)"
                value={newCredential.description}
                onChange={(e) => setNewCredential({ ...newCredential, description: e.target.value })}
                placeholder="What is this credential for?"
                accentColor="pink"
              />
              <Button
                variant="secondary"
                onClick={handleAddCredential}
                disabled={!newCredential.key}
                accentColor="pink"
              >
                <Plus className="w-4 h-4 mr-2 inline" />
                Add Credential
              </Button>
            </div>
          </div>
        </Card>
      </motion.div>

      {/* RAG Settings */}
      <motion.div className="mb-8" variants={itemVariants}>
        <h2 className="text-xl font-semibold text-gray-800 dark:text-white mb-4 flex items-center">
          <Settings className="mr-2 text-green-500" size={20} />
          RAG Settings
        </h2>
        <Card accentColor="green" className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-zinc-400 mb-4">
            Configure Retrieval-Augmented Generation (RAG) strategies for optimal knowledge retrieval.
          </p>
          
          {/* Model Choice */}
          <Select
            label="LLM Model"
            value={ragSettings.MODEL_CHOICE}
            onChange={(e) => setRagSettings({ ...ragSettings, MODEL_CHOICE: e.target.value })}
            options={[
              { value: 'gpt-4o-mini', label: 'GPT-4 Optimized Mini' },
              { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
              { value: 'gpt-4', label: 'GPT-4' },
              { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' }
            ]}
            accentColor="green"
          />
          
          {/* RAG Strategy Toggles */}
          <div className="space-y-3">
            <div className="flex items-start">
              <input
                type="checkbox"
                id="contextualEmbeddings"
                checked={ragSettings.USE_CONTEXTUAL_EMBEDDINGS}
                onChange={(e) => setRagSettings({ ...ragSettings, USE_CONTEXTUAL_EMBEDDINGS: e.target.checked })}
                className="mr-3 mt-1 h-4 w-4 rounded border-zinc-700 bg-black dark:bg-black text-green-500 focus:ring-0 focus:ring-offset-0"
              />
              <label htmlFor="contextualEmbeddings" className="flex-1">
                <span className="text-gray-700 dark:text-zinc-300 font-medium">
                  Use Contextual Embeddings
                </span>
                <p className="text-sm text-gray-600 dark:text-zinc-400 mt-1">
                  Enhances embeddings with contextual information for better retrieval
                </p>
              </label>
            </div>
            
            <div className="flex items-start">
              <input
                type="checkbox"
                id="hybridSearch"
                checked={ragSettings.USE_HYBRID_SEARCH}
                onChange={(e) => setRagSettings({ ...ragSettings, USE_HYBRID_SEARCH: e.target.checked })}
                className="mr-3 mt-1 h-4 w-4 rounded border-zinc-700 bg-black dark:bg-black text-green-500 focus:ring-0 focus:ring-offset-0"
              />
              <label htmlFor="hybridSearch" className="flex-1">
                <span className="text-gray-700 dark:text-zinc-300 font-medium">
                  Use Hybrid Search
                </span>
                <p className="text-sm text-gray-600 dark:text-zinc-400 mt-1">
                  Combines vector similarity search with keyword search for better results
                </p>
              </label>
            </div>
            
            <div className="flex items-start">
              <input
                type="checkbox"
                id="agenticRag"
                checked={ragSettings.USE_AGENTIC_RAG}
                onChange={(e) => setRagSettings({ ...ragSettings, USE_AGENTIC_RAG: e.target.checked })}
                className="mr-3 mt-1 h-4 w-4 rounded border-zinc-700 bg-black dark:bg-black text-green-500 focus:ring-0 focus:ring-offset-0"
              />
              <label htmlFor="agenticRag" className="flex-1">
                <span className="text-gray-700 dark:text-zinc-300 font-medium">
                  Use Agentic RAG
                </span>
                <p className="text-sm text-gray-600 dark:text-zinc-400 mt-1">
                  Enables code example extraction, storage, and specialized code search functionality
                </p>
              </label>
            </div>
            
            <div className="flex items-start">
              <input
                type="checkbox"
                id="reranking"
                checked={ragSettings.USE_RERANKING}
                onChange={(e) => setRagSettings({ ...ragSettings, USE_RERANKING: e.target.checked })}
                className="mr-3 mt-1 h-4 w-4 rounded border-zinc-700 bg-black dark:bg-black text-green-500 focus:ring-0 focus:ring-offset-0"
              />
              <label htmlFor="reranking" className="flex-1">
                <span className="text-gray-700 dark:text-zinc-300 font-medium">
                  Use Reranking
                </span>
                <p className="text-sm text-gray-600 dark:text-zinc-400 mt-1">
                  Applies cross-encoder reranking to improve search result relevance
                </p>
              </label>
            </div>
          </div>
        </Card>
      </motion.div>

      {/* Save Button */}
      <motion.div variants={itemVariants}>
        <Button
          variant="primary"
          accentColor="green"
          className="shadow-lg shadow-emerald-500/20"
          onClick={handleSaveSettings}
          disabled={saving}
        >
          {saving ? (
            <>
              <Loader className="w-4 h-4 mr-2 animate-spin inline" />
              <span>Saving...</span>
            </>
          ) : (
            <>
              <Save className="w-4 h-4 mr-2 inline" />
              <span>Save Settings</span>
            </>
          )}
        </Button>
      </motion.div>
    </motion.div>
  );
};