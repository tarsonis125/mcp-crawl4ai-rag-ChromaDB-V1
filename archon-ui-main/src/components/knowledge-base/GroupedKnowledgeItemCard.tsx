import { useState, useRef, useEffect } from 'react';
import { Link as LinkIcon, Upload, Trash2, RefreshCw, X, Copy, Edit3 } from 'lucide-react';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { knowledgeBaseService, KnowledgeItem, KnowledgeItemMetadata } from '../../services/knowledgeBaseService';
import { useToast } from '../../contexts/ToastContext';

// Define GroupedKnowledgeItem interface locally
interface GroupedKnowledgeItem {
  id: string;
  title: string;
  domain: string;
  items: KnowledgeItem[];
  metadata: KnowledgeItemMetadata;
  created_at: string;
  updated_at: string;
}

// Inline editable field component
interface InlineEditableFieldProps {
  value: string;
  onSave: (value: string) => Promise<void>;
  placeholder?: string;
  multiline?: boolean;
  className?: string;
  truncateLines?: number;
  displayClassName?: string;
}

const InlineEditableField = ({ 
  value, 
  onSave, 
  placeholder, 
  multiline = false, 
  className = "", 
  truncateLines = 1,
  displayClassName = ""
}: InlineEditableFieldProps) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

  useEffect(() => {
    setEditValue(value);
  }, [value]);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleSave = async () => {
    if (editValue.trim() !== value.trim()) {
      setSaving(true);
      try {
        await onSave(editValue.trim());
      } catch (error) {
        console.error('Failed to save:', error);
        setEditValue(value); // Revert on error
      } finally {
        setSaving(false);
      }
    }
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditValue(value);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !multiline) {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Enter' && multiline && e.ctrlKey) {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  };

  if (isEditing) {
    const Component = multiline ? 'textarea' : 'input';
    return (
      <div className="flex items-start gap-2">
        <Component
          ref={inputRef as any}
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleSave}
          placeholder={placeholder}
          className={`flex-1 bg-white/90 dark:bg-black/70 border border-cyan-300 dark:border-cyan-600 rounded px-2 py-1 text-sm focus:outline-none focus:border-cyan-500 resize-none ${className}`}
          disabled={saving}
          rows={multiline ? 3 : undefined}
        />
        {saving && (
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-cyan-500 mt-1"></div>
        )}
      </div>
    );
  }

  // Determine truncation classes
  const truncateClass = truncateLines === 1 ? 'line-clamp-1' : 
                       truncateLines === 2 ? 'line-clamp-2' : 
                       truncateLines === 3 ? 'line-clamp-3' : 
                       `line-clamp-${truncateLines}`;

  return (
    <div 
      className={`group cursor-pointer hover:bg-cyan-50/50 dark:hover:bg-cyan-900/20 rounded px-1 transition-colors ${className}`}
      onClick={() => setIsEditing(true)}
      title="Click to edit"
    >
      <div className="flex items-start gap-2">
        <span className={`flex-1 ${truncateClass} ${displayClassName}`}>
          {value || <span className="text-gray-400 dark:text-gray-600">{placeholder}</span>}
        </span>
        <Edit3 className="w-3 h-3 opacity-0 group-hover:opacity-60 transition-opacity mt-0.5 flex-shrink-0" />
      </div>
    </div>
  );
};

interface GroupedKnowledgeItemCardProps {
  groupedItem: GroupedKnowledgeItem;
  onDelete: (sourceId: string) => void;
}

export const GroupedKnowledgeItemCard = ({
  groupedItem,
  onDelete
}: GroupedKnowledgeItemCardProps) => {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const { showToast } = useToast();

  const isGrouped = groupedItem.items.length > 1;
  const firstItem = groupedItem.items[0];
  const selectedItem = selectedSourceId ? groupedItem.items.find(item => item.id === selectedSourceId) : null;
  const showingGroupView = !selectedItem;
  const displayItem = selectedItem || firstItem;

  // Handle updating individual source items
  const handleUpdateItem = async (sourceId: string, field: 'title' | 'description', value: string) => {
    try {
      const updates: Record<string, any> = {};
      if (field === 'title') {
        updates.title = value;
      } else if (field === 'description') {
        updates.description = value;
      }
      
      await knowledgeBaseService.updateKnowledgeItem(sourceId, updates);
      showToast('Item updated successfully', 'success');
    } catch (error) {
      console.error('Failed to update item:', error);
      showToast('Failed to update item', 'error');
      throw error; // Re-throw to trigger revert in InlineEditableField
    }
  };

  const handleDelete = async () => {
    // Call the main delete handler with the group ID
    await onDelete(groupedItem.id);
    setShowDeleteConfirm(false);
  };

  const statusColorMap = {
    active: 'green',
    processing: 'blue',
    error: 'pink'
  };
  const accentColor = firstItem.metadata.source_type === 'url' ? 'blue' : 'pink';
  
  // Get the type icon
  const TypeIcon = firstItem.metadata.knowledge_type === 'technical' ? 
    ({ className }: { className?: string }) => <svg className={className} fill="currentColor" viewBox="0 0 24 24"><path d="M12 2L2 7V17L12 22L22 17V7L12 2Z"/></svg> :
    ({ className }: { className?: string }) => <svg className={className} fill="currentColor" viewBox="0 0 24 24"><path d="M9,12A3,3 0 0,0 12,9A3,3 0 0,0 12,15A3,3 0 0,0 9,12M12,17A5,5 0 0,1 7,12A5,5 0 0,1 12,7A5,5 0 0,1 17,12A5,5 0 0,1 12,17M12,4.5C7,4.5 2.73,7.61 1,12C2.73,16.39 7,19.5 12,19.5C17,19.5 21.27,16.39 23,12C21.27,7.61 17,4.5 12,4.5Z"/></svg>;
  
  const typeIconColor = firstItem.metadata.knowledge_type === 'technical' ? 'text-blue-500' : 'text-purple-500';

  // Get frequency display for individual items
  const getFrequencyDisplay = (item: KnowledgeItem) => {
    const frequency = item.metadata.update_frequency;
    if (!frequency || frequency === 0) {
      return { icon: <X className="w-3 h-3" />, text: 'Never', color: 'text-gray-500 dark:text-zinc-500' };
    } else if (frequency === 1) {
      return { icon: <RefreshCw className="w-3 h-3" />, text: 'Daily', color: 'text-green-500' };
    } else if (frequency === 7) {
      return { icon: <RefreshCw className="w-3 h-3" />, text: 'Weekly', color: 'text-blue-500' };
    } else if (frequency === 30) {
      return { icon: <RefreshCw className="w-3 h-3" />, text: 'Monthly', color: 'text-purple-500' };
    } else {
      return { icon: <RefreshCw className="w-3 h-3" />, text: `Every ${frequency} days`, color: 'text-gray-500 dark:text-zinc-500' };
    }
  };

  // Delete confirmation modal
  const DeleteConfirmModal = () => (
    <div className="fixed inset-0 bg-gray-500/50 dark:bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
      <Card className="w-full max-w-md">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white mb-4">
          Delete Knowledge Item
        </h3>
        <p className="text-gray-600 dark:text-zinc-400 mb-6">
          Are you sure you want to delete this knowledge item? This action cannot be undone.
        </p>
        <div className="flex justify-end gap-4">
          <button
            onClick={() => setShowDeleteConfirm(false)}
            className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleDelete}
            className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
          >
            Delete
          </button>
        </div>
      </Card>
    </div>
  );

  return (
    <Card accentColor={accentColor} className="h-full flex flex-col">
      {/* Header section - fixed height */}
      <div className="flex items-center gap-2 mb-3">
        {/* Source type icon */}
        {firstItem.metadata.source_type === 'url' ? <LinkIcon className="w-4 h-4 text-blue-500" /> : <Upload className="w-4 h-4 text-pink-500" />}
        {/* Knowledge type icon */}
        <TypeIcon className={`w-4 h-4 ${typeIconColor}`} />
        <div className="flex-1">
          {showingGroupView ? (
            <h3 className="text-gray-800 dark:text-white font-medium line-clamp-1">
              {groupedItem.domain}
            </h3>
          ) : (
            <InlineEditableField
              value={displayItem.title}
              onSave={(value) => handleUpdateItem(displayItem.source_id, 'title', value)}
              placeholder="Enter title..."
              className="text-gray-800 dark:text-white font-medium"
            />
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <button 
            onClick={(e) => {
              e.stopPropagation();
                             const sourceIds = isGrouped 
                ? groupedItem.items.map((item: KnowledgeItem) => item.source_id)
                : [firstItem.source_id];
              const textToCopy = isGrouped ? JSON.stringify(sourceIds, null, 2) : sourceIds[0];
              navigator.clipboard.writeText(textToCopy);
              // Visual feedback
              const button = e.currentTarget;
              const originalHTML = button.innerHTML;
              button.innerHTML = '<div class="flex items-center justify-center text-green-500"><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg></div>';
              setTimeout(() => {
                button.innerHTML = originalHTML;
              }, 2000);
            }} 
            className="w-5 h-5 rounded-full flex items-center justify-center bg-gray-100/80 dark:bg-gray-500/20 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-500/30 hover:shadow-[0_0_10px_rgba(107,114,128,0.3)] transition-all duration-300" 
            title="Copy Source ID(s)"
          >
            <Copy className="w-3 h-3" />
          </button>
          <button 
            onClick={() => setShowDeleteConfirm(true)} 
            className="w-5 h-5 rounded-full flex items-center justify-center bg-red-100/80 dark:bg-red-500/20 text-red-600 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-500/30 hover:shadow-[0_0_10px_rgba(239,68,68,0.3)] transition-all duration-300" 
            title="Delete"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>
      
      {/* Neon Selector - only for grouped items */}
      {isGrouped && (
        <div className="mb-3 relative">
          <button
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            className="w-fit px-4 py-2 bg-gradient-to-r from-blue-500/20 to-purple-500/20 border border-blue-400/50 dark:border-blue-500/50 rounded-lg backdrop-blur-sm transition-all duration-300 hover:shadow-[0_0_15px_rgba(59,130,246,0.4)] dark:hover:shadow-[0_0_15px_rgba(59,130,246,0.6)] focus:outline-none focus:ring-2 focus:ring-blue-500/50"
          >
            <div className="flex items-center gap-3">
              {/* Neon blue status dot */}
              <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_6px_rgba(59,130,246,0.8)]"></div>
              <span className="text-sm font-medium text-gray-800 dark:text-white">
                {selectedItem ? selectedItem.title : `${groupedItem.domain} (${groupedItem.items.length} sources)`}
              </span>
            </div>
          </button>
          
          {/* Dropdown */}
          {isDropdownOpen && (
            <div className="absolute top-full left-0 mt-2 w-full bg-white/95 dark:bg-gray-900/95 border border-gray-200 dark:border-gray-700 rounded-lg backdrop-blur-sm shadow-lg z-10 max-h-48 overflow-y-auto">
              <button
                onClick={() => {
                  setSelectedSourceId(null);
                  setIsDropdownOpen(false);
                }}
                className={`w-full px-4 py-2 text-left hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors ${!selectedItem ? 'bg-blue-50 dark:bg-blue-900/20' : ''}`}
              >
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_4px_rgba(59,130,246,0.6)]"></div>
                  <span className="text-sm">{groupedItem.domain} (Group View)</span>
                </div>
              </button>
                             {groupedItem.items.map((item: KnowledgeItem) => (
                 <button
                   key={item.id}
                   onClick={() => {
                     setSelectedSourceId(item.id);
                     setIsDropdownOpen(false);
                   }}
                   className={`w-full px-4 py-2 text-left hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors ${selectedItem?.id === item.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''}`}
                 >
                   <div className="flex items-center gap-2">
                     <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_4px_rgba(59,130,246,0.6)]"></div>
                     <span className="text-sm truncate">{item.title}</span>
                   </div>
                 </button>
               ))}
            </div>
          )}
        </div>
      )}

      {/* Description section - 3 lines max */}
      <div className="text-gray-600 dark:text-zinc-400 mb-3 min-h-[3rem]">
        {showingGroupView ? (
          <p className="text-xs line-clamp-3 leading-relaxed">
            {`${groupedItem.items.length} sources from ${groupedItem.domain}`}
          </p>
        ) : (
          <InlineEditableField
            value={displayItem.metadata.description || ''}
            onSave={(value) => handleUpdateItem(displayItem.source_id, 'description', value)}
            placeholder="Add description..."
            multiline={true}
            truncateLines={3}
            displayClassName="text-xs leading-relaxed"
          />
        )}
      </div>
      
      {/* Tags section - fixed height for 2 rows */}
      <div className="mb-4 h-16 flex items-start">
        <div className="flex flex-wrap gap-2">
                     {showingGroupView ? (
             // Show combined tags from all items in group
             Array.from(new Set(groupedItem.items.flatMap((item: KnowledgeItem) => item.metadata.tags || []))).slice(0, 4).map((tag: string, index: number) => (
               <Badge key={index} color="purple" variant="outline" className="text-xs">
                 {tag}
               </Badge>
             ))
           ) : (
             // Show tags for selected item
             (displayItem.metadata.tags || []).slice(0, 4).map((tag: string, index: number) => (
               <Badge key={index} color="purple" variant="outline" className="text-xs">
                 {tag}
               </Badge>
             ))
           )}
          {((showingGroupView ? Array.from(new Set(groupedItem.items.flatMap(item => item.metadata.tags || []))) : (displayItem.metadata.tags || [])).length > 4) && (
            <Badge color="purple" variant="outline" className="bg-purple-100/50 dark:bg-purple-900/30 border-dashed text-xs">
              +{(showingGroupView ? Array.from(new Set(groupedItem.items.flatMap(item => item.metadata.tags || []))) : (displayItem.metadata.tags || [])).length - 4} more...
            </Badge>
          )}
        </div>
      </div>
      
      {/* Footer section - pushed to bottom */}
      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-zinc-500 mt-auto">
        <div className="flex items-center gap-3">
          <span>Updated: {new Date(displayItem.updated_at).toLocaleDateString()}</span>
          {!showingGroupView && (() => {
            const frequencyDisplay = getFrequencyDisplay(displayItem);
            return (
              <div className={`flex items-center gap-1 ${frequencyDisplay.color}`}>
                {frequencyDisplay.icon}
                <span>{frequencyDisplay.text}</span>
              </div>
            );
          })()}
        </div>
         <Badge color={statusColorMap[displayItem.metadata.status || 'active'] as 'green' | 'blue' | 'pink'}>
           {(displayItem.metadata.status || 'active').charAt(0).toUpperCase() + (displayItem.metadata.status || 'active').slice(1)}
         </Badge>
      </div>
      
      {showDeleteConfirm && <DeleteConfirmModal />}
    </Card>
  );
}; 