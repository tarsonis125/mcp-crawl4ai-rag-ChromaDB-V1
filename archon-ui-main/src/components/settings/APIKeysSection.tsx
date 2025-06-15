import { useState, useEffect } from 'react';
import { Key, Plus, Trash2, Check, Save, Lock, Unlock } from 'lucide-react';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { credentialsService, Credential } from '../../services/credentialsService';
import { useToast } from '../../contexts/ToastContext';

interface CustomCredential {
  key: string;
  value: string;
  description: string;
  originalValue?: string; // Track original value to detect changes
  hasChanges?: boolean; // Track if there are unsaved changes
  is_encrypted?: boolean; // Track if this credential is encrypted
}

export const APIKeysSection = () => {
  // Not currently used but kept for future integration with system credentials
  const [_credentials, setCredentials] = useState<Credential[]>([]);
  const [customCredentials, setCustomCredentials] = useState<CustomCredential[]>([]);
  const [newCredential, setNewCredential] = useState<CustomCredential>({ key: '', value: '', description: '' });
  const [newCredentialIsSecret, setNewCredentialIsSecret] = useState(false); // Toggle for new credential encryption
  const [showKeys, setShowKeys] = useState(false);
  const [selectedFeature, setSelectedFeature] = useState<string>('core');
  const [loading, setLoading] = useState(true);
  const [savingKeys, setSavingKeys] = useState<Set<string>>(new Set()); // Track which keys are being saved

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
      
      // Load credentials from different categories for better OpenAI API key support
      const apiKeysCredentials = await credentialsService.getCredentialsByCategory('api_keys');
      const customCategoryCredentials = await credentialsService.getCredentialsByCategory('custom');
      
      // Also get all credentials to catch any that might have NULL category (like OPENAI_API_KEY)
      const allDbCredentials = await credentialsService.getAllCredentials();
      const nullCategoryCredentials = allDbCredentials.filter(cred => 
        !cred.category || cred.category === '' || cred.key === 'OPENAI_API_KEY'
      );
      
      // Combine all credential sources
      const combinedCredentials = [
        ...apiKeysCredentials,
        ...customCategoryCredentials,
        ...nullCategoryCredentials
      ];
      
      // Deduplicate credentials by key (in case same key exists in multiple categories)
      const credentialMap = new Map<string, Credential>();
      combinedCredentials.forEach(cred => {
        // Prefer api_keys category for OPENAI_API_KEY, otherwise use first found
        if (!credentialMap.has(cred.key) || 
            (cred.key === 'OPENAI_API_KEY' && cred.category === 'api_keys')) {
          credentialMap.set(cred.key, cred);
        }
      });

      // Convert to array and handle encrypted values
      const customCreds = Array.from(credentialMap.values()).map(cred => {
        let displayValue = cred.value || '';
        
        // Handle encrypted credentials
        if (cred.is_encrypted && !cred.value && cred.encrypted_value) {
          // If we have an encrypted value but no decrypted value, show placeholder
          displayValue = '';
        }
        
        return {
          key: cred.key,
          value: displayValue,
          description: cred.description || '',
          originalValue: displayValue, // Track original value
          hasChanges: false,
          is_encrypted: cred.is_encrypted || false
        };
      });
      
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
      const result = await credentialsService.createCredential({
        key: newCredential.key,
        value: newCredential.value,
        description: newCredential.description,
        is_encrypted: newCredentialIsSecret,
        category: 'api_keys'
      });
      
      const newCred = {
        ...newCredential,
        originalValue: newCredential.value,
        hasChanges: false,
        is_encrypted: newCredentialIsSecret
      };
      
      setCustomCredentials([...customCredentials, newCred]);
      setNewCredential({ key: '', value: '', description: '' });
      setNewCredentialIsSecret(false);
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

  const updateCredentialValue = (key: string, value: string) => {
    // Update local state immediately for responsiveness
    setCustomCredentials(customCredentials.map(cred => {
      if (cred.key === key) {
        return {
          ...cred,
          value,
          hasChanges: value !== cred.originalValue
        };
      }
      return cred;
    }));
  };

  const saveCredentialValue = async (key: string, value: string) => {
    try {
      setSavingKeys(prev => new Set(prev).add(key));
      
      // Find the credential to get its encryption status
      const credential = customCredentials.find(cred => cred.key === key);
      const shouldEncrypt = credential?.is_encrypted || false;
      
      await credentialsService.updateCredential({
        key: key,
        value: value,
        description: '',
        is_encrypted: shouldEncrypt,
        category: 'api_keys'
      });
      
      // Update the original value and clear changes flag
      setCustomCredentials(customCredentials.map(cred => {
        if (cred.key === key) {
          return {
            ...cred,
            originalValue: value,
            hasChanges: false
          };
        }
        return cred;
      }));
      
      showToast(`${key} saved successfully!`, 'success');
    } catch (err) {
      console.error('Failed to update credential:', err);
      showToast(`Failed to save ${key}`, 'error');
    } finally {
      setSavingKeys(prev => {
        const newSet = new Set(prev);
        newSet.delete(key);
        return newSet;
      });
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>, key: string, value: string) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      saveCredentialValue(key, value);
    }
  };

  // Simplified features - comment out for future implementation
  /*
  const features = [
    { id: 'all', name: 'All Features' },
    { id: 'core', name: 'Core' },
    { id: 'projects', name: 'Projects' },
    { id: 'agui', name: 'AG-UI Library' },
    { id: 'agents', name: 'Agents' }
  ];
  */

  // Simplified to just Core for now
  const features = [
    { id: 'core', name: 'Core' }
  ];

  // API keys organized by feature - simplified to just show all for Core
  const getKeysToDisplay = () => {
    // Since we only have Core now, show all credentials
    return customCredentials;
    
    /* Future implementation when we add more features:
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
    */
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
    <div className="space-y-5 my-8">
      <div className="flex items-center mb-4">
        <h2 className="text-xl font-semibold text-gray-800 dark:text-white flex items-center">
          <Key className="mr-2 text-pink-500" size={20} />
          API Keys
        </h2>
      </div>
      <Card accentColor="pink" className="my-6 p-6">
        <div className="space-y-4">

        {/* Description text */}
        <p className="text-sm text-gray-600 dark:text-zinc-400 mb-2">
          Manage your API keys and credentials for various services used by Archon. Press Enter or click the save button to save changes.
        </p>

        {/* Simplified feature filter - just Core highlighted */}
        <div className="flex flex-wrap gap-2 justify-between items-center">
          <div className="flex flex-wrap gap-2">
            {features.map((feature) => (
            <button
              key={feature.id}
              onClick={() => setSelectedFeature(feature.id)}
              className={`
                px-3 py-1.5 rounded-full text-xs transition-all duration-200
                bg-pink-100 dark:bg-pink-900/20 text-pink-600 dark:text-pink-400 ring-1 ring-pink-500/50 shadow-[0_0_8px_rgba(236,72,153,0.3)]
              `}
            >
              {feature.name}
            </button>
          ))}
          </div>
          
          {/* Show Keys button */}
          <Button
            variant="primary"
            accentColor="pink"
            size="sm"
            onClick={() => setShowKeys(!showKeys)}
          >
            {showKeys ? 'Hide Keys' : 'Show Keys'}
          </Button>
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
                  onKeyPress={(e) => handleKeyPress(e, cred.key, cred.value)}
                  placeholder={
                    cred.is_encrypted && cred.value === ''
                      ? `${cred.description || `Enter ${cred.key}`} (encrypted - enter new value to update)`
                      : (cred.description || `Enter ${cred.key}`)
                  }
                  accentColor="pink"
                />
              </div>
              
              {/* Action button - Save if changes detected, Delete if no changes */}
              {cred.hasChanges ? (
                <Button
                  variant="primary"
                  onClick={() => saveCredentialValue(cred.key, cred.value)}
                  accentColor="green"
                  className="mt-6"
                  disabled={savingKeys.has(cred.key)}
                >
                  {savingKeys.has(cred.key) ? (
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                </Button>
              ) : (
                <Button
                  variant="outline"
                  onClick={() => handleDeleteCredential(cred.key)}
                  accentColor="pink"
                  className="mt-6"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              )}
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
            
            {/* Value input with Secret toggle */}
            <div className="relative">
              <Input
                label="Value"
                type="password"
                value={newCredential.value}
                onChange={(e) => setNewCredential({ ...newCredential, value: e.target.value })}
                placeholder="Enter value"
                accentColor="pink"
              />
              
              {/* Secret toggle button */}
              <button
                type="button"
                onClick={() => setNewCredentialIsSecret(!newCredentialIsSecret)}
                className={`
                  absolute right-3 top-8 p-1.5 rounded-md transition-all duration-200
                  ${newCredentialIsSecret 
                    ? 'bg-pink-100 dark:bg-pink-900/20 text-pink-600 dark:text-pink-400' 
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
                  }
                  hover:bg-opacity-80
                `}
                title={newCredentialIsSecret ? 'Secret (encrypted)' : 'Not secret (plain text)'}
              >
                {newCredentialIsSecret ? <Lock className="w-4 h-4" /> : <Unlock className="w-4 h-4" />}
              </button>
              
              {/* Secret toggle label */}
              <label className="absolute right-12 top-8 text-xs text-gray-500 dark:text-gray-400 pointer-events-none">
                Secret
              </label>
            </div>
            
            <Input
              label="Description (optional)"
              value={newCredential.description}
              onChange={(e) => setNewCredential({ ...newCredential, description: e.target.value })}
              placeholder="What is this credential for?"
              accentColor="pink"
            />
            <Button
              variant="outline"
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
        <div className="p-3 mt-6 mb-2 bg-gray-50 dark:bg-black/40 rounded-md flex items-start gap-3">
          <div className="w-5 h-5 text-pink-500 mt-0.5 flex-shrink-0">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" />
            </svg>
          </div>
          <div className="text-sm text-gray-600 dark:text-gray-400">
            <p className="mb-2">
              Use the Secret toggle when adding credentials to automatically encrypt sensitive values. Encrypted credentials are stored securely and only decrypted when needed.
            </p>
            <p>
              <strong>💡 Usage:</strong> Press <kbd className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">Enter</kbd> or click the green save button to save changes.
            </p>
          </div>
        </div>
      </div>
      </Card>
    </div>
  );
};