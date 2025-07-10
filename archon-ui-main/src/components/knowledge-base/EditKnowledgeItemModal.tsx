import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import { X, Save, RefreshCw } from 'lucide-react';
import { Input } from '../ui/Input';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { KnowledgeItem } from '../../services/knowledgeBaseService';
import { knowledgeBaseService } from '../../services/knowledgeBaseService';
import { useToast } from '../../contexts/ToastContext';

interface EditKnowledgeItemModalProps {
  item: KnowledgeItem;
  onClose: () => void;
  onUpdate: () => void;
}

export const EditKnowledgeItemModal: React.FC<EditKnowledgeItemModalProps> = ({
  item,
  onClose,
  onUpdate,
}) => {
  const { showToast } = useToast();
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({
    title: item.title,
  });

  // Handle escape key to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.title.trim()) {
      showToast('Title is required', 'error');
      return;
    }

    setIsLoading(true);
    
    try {
      // Update the knowledge item
      const updates: any = {};
      
      // Only include title if it has changed
      if (formData.title !== item.title) {
        updates.title = formData.title;
      }
      
      await knowledgeBaseService.updateKnowledgeItem(item.source_id, updates);
      
      showToast('Knowledge item updated successfully', 'success');
      onUpdate();
      onClose();
    } catch (error) {
      console.error('Failed to update knowledge item:', error);
      showToast(`Failed to update: ${error.message || 'Unknown error'}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };


  // Using React Portal to render the modal at the root level
  return createPortal(
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 flex items-center justify-center z-50 bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="relative w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Pink accent line at the top */}
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-pink-500 to-purple-500 shadow-[0_0_20px_5px_rgba(236,72,153,0.5)] z-10 rounded-t-xl"></div>
        
        <Card className="relative overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-gray-800 dark:text-white">
              Edit Knowledge Item
            </h2>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Title"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder="Enter title"
              accentColor="pink"
              disabled={isLoading}
            />

            {/* Additional info */}
            <div className="bg-gray-100 dark:bg-zinc-800 rounded-lg p-3 space-y-1">
              <div className="text-sm text-gray-600 dark:text-zinc-400">
                <span className="font-medium">Source:</span> {item.url}
              </div>
              <div className="text-sm text-gray-600 dark:text-zinc-400">
                <span className="font-medium">Type:</span> {item.metadata.source_type === 'url' ? 'URL' : 'File'}
              </div>
              <div className="text-sm text-gray-600 dark:text-zinc-400">
                <span className="font-medium">Last Updated:</span> {new Date(item.updated_at).toLocaleString()}
              </div>
            </div>

            {/* Buttons */}
            <div className="flex justify-end gap-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={onClose}
                disabled={isLoading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                accentColor="pink"
                disabled={isLoading}
                className="flex items-center gap-2"
              >
                {isLoading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4" />
                    Save Changes
                  </>
                )}
              </Button>
            </div>
          </form>
        </Card>
      </motion.div>
    </motion.div>,
    document.body
  );
};