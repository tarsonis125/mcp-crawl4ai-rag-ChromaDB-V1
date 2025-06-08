import React from 'react';
import { Settings, Check } from 'lucide-react';
import { Card } from '../ui/Card';
import { Select } from '../ui/Select';
interface RAGSettingsProps {
  ragSettings: {
    MODEL_CHOICE: string;
    USE_CONTEXTUAL_EMBEDDINGS: boolean;
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
  return <div>
      <div className="flex items-center mb-4">
        <Settings className="mr-2 text-green-500" size={20} />
        <h2 className="text-xl font-semibold text-gray-800 dark:text-white">
          RAG Settings
        </h2>
      </div>
      <Card accentColor="green" className="overflow-hidden">
        <p className="text-sm text-gray-600 dark:text-zinc-400 mb-4">
          Configure Retrieval-Augmented Generation (RAG) strategies for optimal
          knowledge retrieval.
        </p>
        {/* Model Choice */}
        <Select label="LLM Model" value={ragSettings.MODEL_CHOICE} onChange={e => setRagSettings({
        ...ragSettings,
        MODEL_CHOICE: e.target.value
      })} options={[{
        value: 'gpt-4o-mini',
        label: 'GPT-4 Optimized Mini'
      }, {
        value: 'gpt-3.5-turbo',
        label: 'GPT-3.5 Turbo'
      }, {
        value: 'gpt-4',
        label: 'GPT-4'
      }, {
        value: 'gpt-4-turbo',
        label: 'GPT-4 Turbo'
      }]} accentColor="green" />
        {/* RAG Strategy Toggles */}
        <div className="space-y-4 mt-4">
          <CustomCheckbox id="contextualEmbeddings" checked={ragSettings.USE_CONTEXTUAL_EMBEDDINGS} onChange={e => setRagSettings({
          ...ragSettings,
          USE_CONTEXTUAL_EMBEDDINGS: e.target.checked
        })} label="Use Contextual Embeddings" description="Enhances embeddings with contextual information for better retrieval" />
          <CustomCheckbox id="hybridSearch" checked={ragSettings.USE_HYBRID_SEARCH} onChange={e => setRagSettings({
          ...ragSettings,
          USE_HYBRID_SEARCH: e.target.checked
        })} label="Use Hybrid Search" description="Combines vector similarity search with keyword search for better results" />
          <CustomCheckbox id="agenticRag" checked={ragSettings.USE_AGENTIC_RAG} onChange={e => setRagSettings({
          ...ragSettings,
          USE_AGENTIC_RAG: e.target.checked
        })} label="Use Agentic RAG" description="Enables code example extraction, storage, and specialized code search functionality" />
          <CustomCheckbox id="reranking" checked={ragSettings.USE_RERANKING} onChange={e => setRagSettings({
          ...ragSettings,
          USE_RERANKING: e.target.checked
        })} label="Use Reranking" description="Applies cross-encoder reranking to improve search result relevance" />
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
        <label htmlFor={id} className="text-gray-700 dark:text-zinc-300 font-medium cursor-pointer block">
          {label}
        </label>
        <p className="text-sm text-gray-600 dark:text-zinc-400 mt-0.5">
          {description}
        </p>
      </div>
    </div>
  );
};