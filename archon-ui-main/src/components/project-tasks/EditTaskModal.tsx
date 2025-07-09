import React, { memo, useCallback, useMemo, useState, useEffect, useRef } from 'react';
import { X, RefreshCw, Check, Trash2, ChevronDown, ChevronRight, Plus } from 'lucide-react';
import { Button } from '../ui/Button';
import { ArchonLoadingSpinner } from '../animations/Animations';
import { DebouncedInput, FeatureInput } from './TaskInputComponents';
import type { Task } from './TaskTableView';

interface EditTaskModalProps {
  isModalOpen: boolean;
  editingTask: Task | null;
  projectFeatures: any[];
  isLoadingFeatures: boolean;
  isLoadingSubtasks: boolean;
  isSavingTask: boolean;
  tempSubtasks: Omit<Task, 'id'>[];
  isSubtasksExpanded: boolean;
  onClose: () => void;
  onSave: (task: Task) => Promise<void>;
  onTempSubtaskAdd: (subtask: Omit<Task, 'id'>) => void;
  onTempSubtaskUpdate: (index: number, updates: Partial<Omit<Task, 'id'>>) => void;
  onTempSubtaskDelete: (index: number) => void;
  onSubtasksExpandedChange: (expanded: boolean) => void;
  getTasksForPrioritySelection: (status: Task['status']) => Array<{value: number, label: string}>;
}

const ASSIGNEE_OPTIONS = ['User', 'Archon', 'AI IDE Agent'] as const;

// Removed debounce utility - now using DebouncedInput component

export const EditTaskModal = memo(({
  isModalOpen,
  editingTask,
  projectFeatures,
  isLoadingFeatures,
  isLoadingSubtasks,
  isSavingTask,
  tempSubtasks,
  isSubtasksExpanded,
  onClose,
  onSave,
  onTempSubtaskAdd,
  onTempSubtaskUpdate,
  onTempSubtaskDelete,
  onSubtasksExpandedChange,
  getTasksForPrioritySelection
}: EditTaskModalProps) => {
  const [localTask, setLocalTask] = useState<Task | null>(null);
  const [newSubtaskTitle, setNewSubtaskTitle] = useState('');
  
  // Diagnostic: Track render count
  const renderCount = useRef(0);
  
  useEffect(() => {
    renderCount.current++;
    console.log(`[EditTaskModal] Render #${renderCount.current}`, {
      localTask: localTask?.title,
      isModalOpen,
      timestamp: Date.now()
    });
  });
  
  // Sync local state with editingTask when it changes
  useEffect(() => {
    if (editingTask) {
      setLocalTask(editingTask);
    }
  }, [editingTask]);
  
  const priorityOptions = useMemo(() => {
    console.log(`[EditTaskModal] Recalculating priorityOptions for status: ${localTask?.status || 'backlog'}`);
    return getTasksForPrioritySelection(localTask?.status || 'backlog');
  }, [localTask?.status, getTasksForPrioritySelection]);

  // Memoized handlers for input changes
  const handleTitleChange = useCallback((value: string) => {
    console.log('[EditTaskModal] Title changed via DebouncedInput:', value);
    setLocalTask(prev => prev ? { ...prev, title: value } : null);
  }, []);
  
  const handleDescriptionChange = useCallback((value: string) => {
    console.log('[EditTaskModal] Description changed via DebouncedInput:', value);
    setLocalTask(prev => prev ? { ...prev, description: value } : null);
  }, []);
  
  const handleFeatureChange = useCallback((value: string) => {
    console.log('[EditTaskModal] Feature changed via FeatureInput:', value);
    setLocalTask(prev => prev ? { ...prev, feature: value } : null);
  }, []);
  
  const handleStatusChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    const newStatus = e.target.value as Task['status'];
    const newOrder = getTasksForPrioritySelection(newStatus)[0]?.value || 1;
    setLocalTask(prev => prev ? { ...prev, status: newStatus, task_order: newOrder } : null);
  }, [getTasksForPrioritySelection]);
  
  const handlePriorityChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setLocalTask(prev => prev ? { ...prev, task_order: parseInt(e.target.value) } : null);
  }, []);
  
  const handleAssigneeChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setLocalTask(prev => prev ? {
      ...prev,
      assignee: { name: e.target.value as 'User' | 'Archon' | 'AI IDE Agent', avatar: '' }
    } : null);
  }, []);
  
  const handleSave = useCallback(() => {
    if (localTask) {
      onSave(localTask);
    }
  }, [localTask, onSave]);
  
  const handleClose = useCallback(() => {
    onClose();
  }, [onClose]);
  
  const handleSubtasksToggle = useCallback(() => {
    onSubtasksExpandedChange(!isSubtasksExpanded);
  }, [isSubtasksExpanded, onSubtasksExpandedChange]);

  if (!isModalOpen) return null;

  return (
    <div className="fixed inset-0 bg-gray-500/50 dark:bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="relative p-6 rounded-md backdrop-blur-md w-full max-w-2xl bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border border-gray-200 dark:border-zinc-800/50 shadow-[0_10px_30px_-15px_rgba(0,0,0,0.1)] dark:shadow-[0_10px_30px_-15px_rgba(0,0,0,0.7)] before:content-[''] before:absolute before:top-0 before:left-0 before:right-0 before:h-[2px] before:rounded-t-[4px] before:bg-gradient-to-r before:from-cyan-500 before:to-fuchsia-500 before:shadow-[0_0_10px_2px_rgba(34,211,238,0.4)] dark:before:shadow-[0_0_20px_5px_rgba(34,211,238,0.7)] after:content-[''] after:absolute after:top-0 after:left-0 after:right-0 after:h-16 after:bg-gradient-to-b after:from-cyan-100 after:to-white dark:after:from-cyan-500/20 dark:after:to-fuchsia-500/5 after:rounded-t-md after:pointer-events-none">
        <div className="relative z-10">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-fuchsia-500 text-transparent bg-clip-text">
              {editingTask?.id ? 'Edit Task' : 'New Task'}
            </h3>
            <button onClick={handleClose} className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-white transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-gray-700 dark:text-gray-300 mb-1">Title</label>
              <DebouncedInput
                value={localTask?.title || ''}
                onChange={handleTitleChange}
                className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white rounded-md py-2 px-3 focus:outline-none focus:border-cyan-400 focus:shadow-[0_0_10px_rgba(34,211,238,0.2)] transition-all duration-300"
              />
            </div>

            <div>
              <label className="block text-gray-700 dark:text-gray-300 mb-1">Description</label>
              <DebouncedInput
                value={localTask?.description || ''}
                onChange={handleDescriptionChange}
                type="textarea"
                rows={5}
                className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-white rounded-md py-2 px-3 focus:outline-none focus:border-cyan-400 focus:shadow-[0_0_10px_rgba(34,211,238,0.2)] transition-all duration-300"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-gray-700 dark:text-gray-300 mb-1">Status</label>
                <select 
                  value={localTask?.status || 'backlog'} 
                  onChange={handleStatusChange}
                  className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-white rounded-md py-2 px-3 focus:outline-none focus:border-cyan-400 focus:shadow-[0_0_10px_rgba(34,211,238,0.2)] transition-all duration-300"
                >
                  <option value="backlog">Backlog</option>
                  <option value="in-progress">In Process</option>
                  <option value="review">Review</option>
                  <option value="complete">Complete</option>
                </select>
              </div>

              <div>
                <label className="block text-gray-700 dark:text-gray-300 mb-1">Priority</label>
                <select 
                  value={localTask?.task_order || 1} 
                  onChange={handlePriorityChange}
                  className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-white rounded-md py-2 px-3 focus:outline-none focus:border-cyan-400 focus:shadow-[0_0_10px_rgba(34,211,238,0.2)] transition-all duration-300"
                >
                  {priorityOptions.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-gray-700 dark:text-gray-300 mb-1">Assignee</label>
                <select 
                  value={localTask?.assignee?.name || 'User'} 
                  onChange={handleAssigneeChange}
                  className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-white rounded-md py-2 px-3 focus:outline-none focus:border-cyan-400 focus:shadow-[0_0_10px_rgba(34,211,238,0.2)] transition-all duration-300"
                >
                  {ASSIGNEE_OPTIONS.map(option => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-gray-700 dark:text-gray-300 mb-1">Feature</label>
                <FeatureInput
                  value={localTask?.feature || ''}
                  onChange={handleFeatureChange}
                  projectFeatures={projectFeatures}
                  isLoadingFeatures={isLoadingFeatures}
                  placeholder="Type feature name"
                  className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-white rounded-md py-2 px-3 pr-10 focus:outline-none focus:border-cyan-400 focus:shadow-[0_0_10px_rgba(34,211,238,0.2)] transition-all duration-300"
                />
              </div>
            </div>
          </div>

          {/* Subtasks Section */}
          <div className="mt-6 border-t border-gray-200 dark:border-gray-700 pt-6">
            <button
              onClick={handleSubtasksToggle}
              className="flex items-center justify-between w-full mb-4 text-left hover:bg-gray-50 dark:hover:bg-gray-800 p-2 rounded-lg transition-colors"
            >
              <div className="flex items-center gap-2">
                <h4 className="text-lg font-semibold text-gray-800 dark:text-gray-200">
                  Subtasks
                </h4>
                {tempSubtasks.length > 0 && (
                  <span className="px-2 py-1 text-xs bg-blue-200 dark:bg-blue-700 text-blue-600 dark:text-blue-400 rounded-full">
                    {tempSubtasks.length}
                  </span>
                )}
                {isLoadingSubtasks && (
                  <RefreshCw className="w-4 h-4 animate-spin text-cyan-400" />
                )}
              </div>
              {isSubtasksExpanded ? (
                <ChevronDown className="w-5 h-5 text-gray-500 dark:text-gray-400" />
              ) : (
                <ChevronRight className="w-5 h-5 text-gray-500 dark:text-gray-400" />
              )}
            </button>
            
            {isSubtasksExpanded && (
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {/* Temporary Subtasks */}
                {tempSubtasks.map((subtask, index) => (
                  <div key={index} className="flex items-center gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border-l-4 border-blue-500">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900 dark:text-white truncate">
                          {subtask.title}
                        </span>
                        <span className={`px-2 py-1 text-xs rounded-full ${
                          subtask.status === 'complete' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
                          subtask.status === 'in-progress' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
                          subtask.status === 'review' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' :
                          'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                        }`}>
                          {subtask.status}
                        </span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {subtask.assignee?.name || 'User'}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => onTempSubtaskUpdate(index, { 
                          status: subtask.status === 'complete' ? 'backlog' : 'complete' 
                        })}
                        className={`p-1 rounded-full transition-colors ${
                          subtask.status === 'complete' 
                            ? 'bg-gray-200 text-gray-500 hover:bg-gray-300 dark:bg-gray-600 dark:text-gray-400' 
                            : 'bg-green-100 text-green-600 hover:bg-green-200 dark:bg-green-900 dark:text-green-400'
                        }`}
                      >
                        <Check className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => onTempSubtaskDelete(index)}
                        className="p-1 rounded-full bg-red-100 text-red-600 hover:bg-red-200 dark:bg-red-900 dark:text-red-400 transition-colors"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))}
                
                {/* Add New Subtask Row */}
                <div className="flex items-center gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-700">
                  <input
                    type="text"
                    value={newSubtaskTitle}
                    onChange={(e) => setNewSubtaskTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && newSubtaskTitle.trim()) {
                        onTempSubtaskAdd({
                          title: newSubtaskTitle,
                          description: '',
                          status: 'backlog',
                          assignee: { name: 'AI IDE Agent', avatar: '' },
                          feature: localTask?.feature || '',
                          featureColor: '#3b82f6',
                          task_order: 1
                        });
                        setNewSubtaskTitle('');
                      }
                    }}
                    placeholder="Add subtask..."
                    className="flex-1 bg-white/90 dark:bg-black/90 border border-blue-300 dark:border-blue-600 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500 focus:shadow-[0_0_5px_rgba(59,130,246,0.3)]"
                  />
                  <button
                    onClick={() => {
                      if (newSubtaskTitle.trim()) {
                        onTempSubtaskAdd({
                          title: newSubtaskTitle,
                          description: '',
                          status: 'backlog',
                          assignee: { name: 'AI IDE Agent', avatar: '' },
                          feature: localTask?.feature || '',
                          featureColor: '#3b82f6',
                          task_order: 1
                        });
                        setNewSubtaskTitle('');
                      }
                    }}
                    disabled={!newSubtaskTitle.trim()}
                    className="p-2 rounded-full bg-blue-500 text-white hover:bg-blue-600 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3 mt-6">
            <Button onClick={handleClose} variant="ghost" disabled={isSavingTask}>Cancel</Button>
            <Button 
              onClick={handleSave} 
              variant="primary" 
              accentColor="cyan" 
              className="shadow-lg shadow-cyan-500/20"
              disabled={isSavingTask}
            >
              {isSavingTask ? (
                <span className="flex items-center">
                  <ArchonLoadingSpinner size="sm" className="mr-2" />
                  {localTask?.id ? 'Saving...' : 'Creating...'}
                </span>
              ) : (
                localTask?.id ? 'Save Changes' : 'Create Task'
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}, (prevProps, nextProps) => {
  // Custom comparison function to prevent unnecessary re-renders
  // Only re-render if these specific props change
  const isEqual = (
    prevProps.isModalOpen === nextProps.isModalOpen &&
    prevProps.editingTask?.id === nextProps.editingTask?.id &&
    prevProps.editingTask?.title === nextProps.editingTask?.title &&
    prevProps.editingTask?.description === nextProps.editingTask?.description &&
    prevProps.editingTask?.status === nextProps.editingTask?.status &&
    prevProps.editingTask?.assignee?.name === nextProps.editingTask?.assignee?.name &&
    prevProps.editingTask?.feature === nextProps.editingTask?.feature &&
    prevProps.editingTask?.task_order === nextProps.editingTask?.task_order &&
    prevProps.isSavingTask === nextProps.isSavingTask &&
    prevProps.isLoadingFeatures === nextProps.isLoadingFeatures &&
    prevProps.isLoadingSubtasks === nextProps.isLoadingSubtasks &&
    prevProps.tempSubtasks.length === nextProps.tempSubtasks.length &&
    prevProps.isSubtasksExpanded === nextProps.isSubtasksExpanded &&
    prevProps.projectFeatures === nextProps.projectFeatures // Reference equality check
  );
  
  if (!isEqual) {
    console.log('[EditTaskModal] Props changed, re-rendering');
  }
  
  return isEqual;
});

EditTaskModal.displayName = 'EditTaskModal';