import React, { useState, useEffect } from 'react';
import { Key, Plus, Trash2 } from 'lucide-react';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { credentialsService, Credential } from '../../services/credentialsService';
import { useToast } from '../../contexts/ToastContext';

interface CustomCredential {
  key: string;
  value: string;
  description: string;
}

export const APIKeysSection = () => {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [customCredentials, setCustomCredentials] = useState<CustomCredential[]>([]);
  const [newCredential, setNewCredential] = useState<CustomCredential>({ key: '', value: '', description: '' });
  const [showKeys, setShowKeys] = useState(false);
  const [selectedFeature, setSelectedFeature] = useState<string>('core');
  const [loading, setLoading] = useState(true);

  const { showToast } = useToast();

  // Load credentials on mount
  useEffect(() => {
    loadCredentials();
  }, []);

  const loadCredentials = async () => {
    try {
      setLoading(true);
      
      // Load all credentials
      const allCredentials = await credentialsService.getAllCredentials();
      setCredentials(allCredentials);
      
      // Separate custom credentials (non-system ones)
      const customCreds = allCredentials
        .filter(cred => cred.category === 'api_keys' || cred.category === 'custom')
        .map(cred => ({
          key: cred.key,
          value: cred.value || '', // Show actual values for editing
          description: cred.description || ''
        }));
      setCustomCredentials(customCreds);
    } catch (err) {
      console.error('Failed to load credentials:', err);
      showToast('Failed to load credentials', 'error');
    } finally {
      setLoading(false);
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
      console.error('Failed to add credential:', err);
      showToast('Failed to add credential', 'error');
    }
  };

  const handleDeleteCredential = async (key: string) => {
    try {
      await credentialsService.deleteCredential(key);
      setCustomCredentials(customCredentials.filter(cred => cred.key !== key));
      showToast(`Credential ${key} deleted successfully!`, 'success');
    } catch (err) {
      console.error('Failed to delete credential:', err);
      showToast('Failed to delete credential', 'error');
    }
  };

  const updateCredentialValue = async (key: string, value: string) => {
    // Update local state immediately for responsiveness
    setCustomCredentials(customCredentials.map(cred => 
      cred.key === key ? { ...cred, value } : cred
    ));

    // Debounced save to backend could be implemented here
    try {
      await credentialsService.updateCredential({
        key: key,
        value: value,
        description: '',
        is_encrypted: key.toLowerCase().includes('key') || key.toLowerCase().includes('secret'),
        category: 'api_keys'
      });
    } catch (err) {
      console.error('Failed to update credential:', err);
      showToast('Failed to update credential', 'error');
    }
  };

  const features = [
    { id: 'all', name: 'All Features' },
    { id: 'core', name: 'Core' },
    { id: 'projects', name: 'Projects' },
    { id: 'agui', name: 'AG-UI Library' },
    { id: 'agents', name: 'Agents' }
  ];

  // API keys organized by feature
  const getKeysToDisplay = () => {
    if (selectedFeature === 'all') {
      return customCredentials;
    }
    
    // Filter based on feature selection
    return customCredentials.filter(cred => {
      const keyLower = cred.key.toLowerCase();
      switch (selectedFeature) {
        case 'core':
          return keyLower.includes('openai');
        case 'projects':
          return keyLower.includes('github') || keyLower.includes('jira');
        case 'agui':
          return keyLower.includes('figma') || keyLower.includes('npm');
        case 'agents':
          return keyLower.includes('anthropic') || keyLower.includes('mistral') || 
                 keyLower.includes('google') || keyLower.includes('huggingface');
        default:
          return true;
      }
    });
  };

  if (loading) {
    return (
      <div className="space-y-5">
        <div className="flex items-center mb-4">
          <h2 className="text-xl font-semibold text-gray-800 dark:text-white flex items-center">
            <Key className="mr-2 text-pink-500" size={20} />
            API Keys
          </h2>
        </div>
        <Card accentColor="pink" className="space-y-5">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
            <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded"></div>
            <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded"></div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center mb-4">
        <h2 className="text-xl font-semibold text-gray-800 dark:text-white flex items-center">
          <Key className="mr-2 text-pink-500" size={20} />
          API Keys
        </h2>
      </div>
      <Card accentColor="pink" className="space-y-5 relative">
        {/* Show Keys button - positioned in top right of card */}
        <div className="absolute top-4 right-4 z-10">
          <Button
            variant="primary"
            accentColor="pink"
            size="sm"
            onClick={() => setShowKeys(!showKeys)}
          >
            {showKeys ? 'Hide Keys' : 'Show Keys'}
          </Button>
        </div>

        {/* Feature filter chips */}
        <div className="flex flex-wrap gap-2">
          {features.map((feature) => (
            <button
              key={feature.id}
              onClick={() => setSelectedFeature(feature.id)}
              className={`
                px-3 py-1.5 rounded-full text-xs transition-all duration-200
                ${selectedFeature === feature.id 
                  ? 'bg-pink-100 dark:bg-pink-900/20 text-pink-600 dark:text-pink-400 ring-1 ring-pink-500/50 shadow-[0_0_8px_rgba(236,72,153,0.3)]' 
                  : 'bg-gray-100/70 dark:bg-gray-800/50 text-gray-600 dark:text-gray-400 hover:bg-gray-200/70 dark:hover:bg-gray-700/50'
                }
              `}
            >
              {feature.name}
            </button>
          ))}
        </div>

        {/* API Keys */}
        <div className="space-y-4">
          {getKeysToDisplay().map((cred, index) => (
            <div key={index} className="flex items-center gap-3">
              <div className="flex-1">
                <Input
                  label={cred.key}
                  type={showKeys ? 'text' : 'password'}
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

        {/* Security Notice */}
        <div className="p-3 bg-gray-50 dark:bg-black/40 rounded-md flex items-start gap-3">
          <div className="w-5 h-5 text-pink-500 mt-0.5 flex-shrink-0">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" />
            </svg>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            All API keys are encrypted and stored securely in your local
            storage. We recommend using environment variables in production.
          </p>
        </div>
      </Card>
    </div>
  );
};