import React, { useState } from 'react';
import { Settings, Check, Save, Loader } from 'lucide-react';
import { Card } from '../ui/Card';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { useToast } from '../../contexts/ToastContext';
import { credentialsService } from '../../services/credentialsService';

interface RAGSettingsProps {
  ragSettings: {
    MODEL_CHOICE: string;
    USE_CONTEXTUAL_EMBEDDINGS: boolean;
    CONTEXTUAL_EMBEDDINGS_MAX_WORKERS: number;
    USE_HYBRID_SEARCH: boolean;
    USE_AGENTIC_RAG: boolean;
    USE_RERANKING: boolean;
  };
  setRagSettings: (settings: any) => void;
}

export const RAGSettings = ({
  ragSettings,
  setRagSettings
}: RAGSettingsProps) => {
  const [saving, setSaving] = useState(false);
  const { showToast } = useToast();
  return <div>
      <div className="flex items-center mb-4">
        <Settings className="mr-2 text-green-500 filter drop-shadow-[0_0_8px_rgba(34,197,94,0.8)]" size={20} />
        <h2 className="text-xl font-semibold text-white">
          RAG Settings
        </h2>
      </div>
      <Card accentColor="green" className="overflow-hidden">
        {/* Description */}
        <p className="text-sm text-gray-600 dark:text-zinc-400 mb-6">
          Configure Retrieval-Augmented Generation (RAG) strategies for optimal
          knowledge retrieval.
        </p>
        
        {/* First row: LLM Model (3/4) and Save Settings (1/4) */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="col-span-3">
            <Input 
              label="LLM Model - LLM for summaries and contextual embeddings" 
              value={ragSettings.MODEL_CHOICE} 
              onChange={e => setRagSettings({
                ...ragSettings,
                MODEL_CHOICE: e.target.value
              })} 
              placeholder="e.g., gpt-4.1-nano"
              accentColor="green" 
            />
          </div>
          <div className="flex items-end">
            <Button 
              variant="outline" 
              accentColor="green" 
              icon={saving ? <Loader className="w-4 h-4 mr-1 animate-spin" /> : <Save className="w-4 h-4 mr-1" />}
              className="w-full whitespace-nowrap"
              size="md"
              onClick={async () => {
                try {
                  setSaving(true);
                  await credentialsService.updateRagSettings(ragSettings);
                  showToast('RAG settings saved successfully!', 'success');
                } catch (err) {
                  console.error('Failed to save RAG settings:', err);
                  showToast('Failed to save settings', 'error');
                } finally {
                  setSaving(false);
                }
              }}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Settings'}
            </Button>
          </div>
        </div>
        
        {/* Second row: Contextual Embeddings, Max Workers, and description */}
        <div className="grid grid-cols-8 gap-4 mb-4">
          <div className="col-span-4">
            <CustomCheckbox 
              id="contextualEmbeddings" 
              checked={ragSettings.USE_CONTEXTUAL_EMBEDDINGS} 
              onChange={e => setRagSettings({
                ...ragSettings,
                USE_CONTEXTUAL_EMBEDDINGS: e.target.checked
              })} 
              label="Use Contextual Embeddings" 
              description="Enhances embeddings with contextual information for better retrieval" 
            />
          </div>
          <div className="col-span-2">
            {ragSettings.USE_CONTEXTUAL_EMBEDDINGS && (
              <>
                <label className="block text-sm font-medium text-gray-700 dark:text-zinc-300 mb-2">
                  Max Workers
                </label>
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={ragSettings.CONTEXTUAL_EMBEDDINGS_MAX_WORKERS}
                  onChange={e => setRagSettings({
                    ...ragSettings,
                    CONTEXTUAL_EMBEDDINGS_MAX_WORKERS: parseInt(e.target.value, 10) || 3
                  })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-md 
                    bg-white dark:bg-gray-800 text-gray-900 dark:text-white
                    focus:ring-2 focus:ring-green-500 focus:border-green-500"
                />
              </>
            )}
          </div>
          <div className="col-span-2">
            {ragSettings.USE_CONTEXTUAL_EMBEDDINGS && (
              <p className="text-xs text-gray-600 dark:text-zinc-400 mt-8">
                Controls parallel processing to reduce API rate limits (1-20)
              </p>
            )}
          </div>
        </div>
        
        {/* Third row: Hybrid Search and Agentic RAG */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <CustomCheckbox 
              id="hybridSearch" 
              checked={ragSettings.USE_HYBRID_SEARCH} 
              onChange={e => setRagSettings({
                ...ragSettings,
                USE_HYBRID_SEARCH: e.target.checked
              })} 
              label="Use Hybrid Search" 
              description="Combines vector similarity search with keyword search for better results" 
            />
          </div>
          <div>
            <CustomCheckbox 
              id="agenticRag" 
              checked={ragSettings.USE_AGENTIC_RAG} 
              onChange={e => setRagSettings({
                ...ragSettings,
                USE_AGENTIC_RAG: e.target.checked
              })} 
              label="Use Agentic RAG" 
              description="Enables code extraction and specialized search for technical content" 
            />
          </div>
        </div>
        
        {/* Fourth row: Use Reranking */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <CustomCheckbox 
              id="reranking" 
              checked={ragSettings.USE_RERANKING} 
              onChange={e => setRagSettings({
                ...ragSettings,
                USE_RERANKING: e.target.checked
              })} 
              label="Use Reranking" 
              description="Applies cross-encoder reranking to improve search result relevance" 
            />
          </div>
          <div>{/* Empty column */}</div>
        </div>
      </Card>
    </div>;
};

interface CustomCheckboxProps {
  id: string;
  checked: boolean;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  label: string;
  description: string;
}

const CustomCheckbox = ({
  id,
  checked,
  onChange,
  label,
  description
}: CustomCheckboxProps) => {
  return (
    <div className="flex items-start group">
      <div className="relative flex items-center h-5 mt-1">
        <input 
          type="checkbox" 
          id={id} 
          checked={checked} 
          onChange={onChange} 
          className="sr-only peer" 
        />
        <label 
          htmlFor={id}
          className="relative w-5 h-5 rounded-md transition-all duration-200 cursor-pointer
            bg-gradient-to-b from-white/80 to-white/60 dark:from-white/5 dark:to-black/40
            border border-gray-300 dark:border-gray-700
            peer-checked:border-green-500 dark:peer-checked:border-green-500/50
            peer-checked:bg-gradient-to-b peer-checked:from-green-500/20 peer-checked:to-green-600/20
            group-hover:border-green-500/50 dark:group-hover:border-green-500/30
            peer-checked:shadow-[0_0_10px_rgba(34,197,94,0.2)] dark:peer-checked:shadow-[0_0_15px_rgba(34,197,94,0.3)]"
        >
          <Check className={`
              w-3.5 h-3.5 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
              transition-all duration-200 text-green-500 pointer-events-none
              ${checked ? 'opacity-100 scale-100' : 'opacity-0 scale-50'}
            `} />
        </label>
      </div>
      <div className="ml-3 flex-1">
        <label htmlFor={id} className="text-gray-700 dark:text-zinc-300 font-medium cursor-pointer block text-sm">
          {label}
        </label>
        <p className="text-xs text-gray-600 dark:text-zinc-400 mt-0.5 leading-tight">
          {description}
        </p>
      </div>
    </div>
  );
};