import { useState } from 'react';
import { Save } from 'lucide-react';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/Button';
import { useStaggeredEntrance } from '../hooks/useStaggeredEntrance';
import { FeaturesSection } from '../components/settings/FeaturesSection';
import { APIKeysSection } from '../components/settings/APIKeysSection';
import { RAGSettings } from '../components/settings/RAGSettings';
import { TestStatus } from '../components/settings/TestStatus';
export const SettingsPage = () => {
  // Use staggered entrance animation
  const {
    isVisible,
    containerVariants,
    itemVariants,
    titleVariants
  } = useStaggeredEntrance([1, 2, 3, 4], 0.15);
  const [ragSettings, setRagSettings] = useState({
    MODEL_CHOICE: 'gpt-4-turbo',
    USE_CONTEXTUAL_EMBEDDINGS: true,
    USE_HYBRID_SEARCH: true,
    USE_AGENTIC_RAG: false,
    USE_RERANKING: true
  });
  return <motion.div initial="hidden" animate={isVisible ? 'visible' : 'hidden'} variants={containerVariants} className="w-full">
      {/* Header with Save Button */}
      <motion.div className="flex justify-between items-center mb-8" variants={itemVariants}>
        <motion.h1 className="text-3xl font-bold text-gray-800 dark:text-white" variants={titleVariants}>
          Settings
        </motion.h1>
        <Button variant="primary" accentColor="green" icon={<Save className="w-4 h-4" />}>
          Save Settings
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
        <div className="space-y-6">
          <motion.div variants={itemVariants}>
            <APIKeysSection />
          </motion.div>
          <motion.div variants={itemVariants}>
            <TestStatus />
          </motion.div>
        </div>
      </div>
    </motion.div>;
};