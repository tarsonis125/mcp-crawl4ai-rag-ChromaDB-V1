import React, { useState, useEffect } from 'react';
import { Save, Loader } from 'lucide-react';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/Button';
import { useToast } from '../contexts/ToastContext';
import { useStaggeredEntrance } from '../hooks/useStaggeredEntrance';
import { FeaturesSection } from '../components/settings/FeaturesSection';
import { APIKeysSection } from '../components/settings/APIKeysSection';
import { RAGSettings } from '../components/settings/RAGSettings';
import { TestStatus } from '../components/settings/TestStatus';
import { credentialsService, RagSettings } from '../services/credentialsService';

export const SettingsPage = () => {
  const [ragSettings, setRagSettings] = useState<RagSettings>({
    USE_CONTEXTUAL_EMBEDDINGS: false,
    USE_HYBRID_SEARCH: false,
    USE_AGENTIC_RAG: false,
    USE_RERANKING: false,
    MODEL_CHOICE: 'gpt-4o-mini'
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { showToast } = useToast();
  
  // Use staggered entrance animation
  const { isVisible, containerVariants, itemVariants, titleVariants } = useStaggeredEntrance(
    [1, 2, 3, 4],
    0.15
  );

  // Load settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      setError(null);
      
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
      className="w-full"
    >
      {/* Header with Save Button */}
      <motion.div className="flex justify-between items-center mb-8" variants={itemVariants}>
        <motion.h1
          className="text-3xl font-bold text-gray-800 dark:text-white"
          variants={titleVariants}
        >
          Settings
        </motion.h1>
        <Button
          variant="primary"
          accentColor="green"
          icon={saving ? <Loader className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          onClick={handleSaveSettings}
          disabled={saving}
        >
          {saving ? 'Saving...' : 'Save Settings'}
        </Button>
      </motion.div>

      {/* Main content with two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column */}
        <div className="space-y-6">
          <motion.div variants={itemVariants}>
            <FeaturesSection />
          </motion.div>
          <motion.div variants={itemVariants}>
            <RAGSettings ragSettings={ragSettings} setRagSettings={setRagSettings} />
          </motion.div>
        </div>

        {/* Right Column */}
        <div className="space-y-10">
          <motion.div variants={itemVariants} className="py-6">
            <APIKeysSection />
          </motion.div>
          <motion.div variants={itemVariants}>
            <TestStatus />
          </motion.div>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <motion.div
          variants={itemVariants}
          className="mt-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg"
        >
          <p className="text-red-600 dark:text-red-400">{error}</p>
        </motion.div>
      )}
    </motion.div>
  );
};