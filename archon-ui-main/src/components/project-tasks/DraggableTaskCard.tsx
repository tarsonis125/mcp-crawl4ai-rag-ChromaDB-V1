import React, { useRef, useState, useCallback } from 'react';
import { useDrag, useDrop } from 'react-dnd';
import { Edit, Trash2, RefreshCw, Tag, User, Bot, Clipboard } from 'lucide-react';
import { Task } from './TaskTableView';
import { ItemTypes, getAssigneeIcon, getAssigneeGlow, getOrderColor, getOrderGlow } from '../../lib/task-utils';

export interface DraggableTaskCardProps {
  task: Task;
  index: number;
  onView: () => void;
  onComplete: () => void;
  onDelete: (task: Task) => void;
  onTaskReorder: (taskId: string, newOrder: number, status: Task['status']) => void;
  tasksInStatus: Task[];
  allTasks?: Task[];
  hoveredTaskId?: string | null;
  onTaskHover?: (taskId: string | null) => void;
  showSubtasks?: boolean;
}

export const DraggableTaskCard = ({
  task,
  index,
  onView,
  onDelete,
  onTaskReorder,
  allTasks = [],
  hoveredTaskId,
  onTaskHover,
  showSubtasks = false,
}: DraggableTaskCardProps) => {
  // Use useCallback to stabilize the state setter
  const [expandedSubtask, setExpandedSubtask] = useState<string | null>(null);
  
  const handleSubtaskClick = useCallback((subtaskId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedSubtask(prev => prev === subtaskId ? null : subtaskId);
  }, []); // Empty dependency array to keep it stable
  
  const [{ isDragging }, drag] = useDrag({
    type: ItemTypes.TASK,
    item: { id: task.id, status: task.status, index },
    collect: (monitor) => ({
      isDragging: !!monitor.isDragging()
    })
  });

  const [, drop] = useDrop({
    accept: ItemTypes.TASK,
    hover: (draggedItem: { id: string; status: Task['status']; index: number }, monitor) => {
      if (!monitor.isOver({ shallow: true })) return;
      if (draggedItem.id === task.id) return;
      if (draggedItem.status !== task.status) return;
      
      const draggedIndex = draggedItem.index;
      const hoveredIndex = index;
      
      if (draggedIndex === hoveredIndex) return;
      
      console.log('BOARD HOVER: Moving task', draggedItem.id, 'from index', draggedIndex, 'to', hoveredIndex, 'in status', task.status);
      
      // Move the task immediately for visual feedback (same pattern as table view)
      onTaskReorder(draggedItem.id, hoveredIndex, task.status);
      
      // Update the dragged item's index to prevent re-triggering
      draggedItem.index = hoveredIndex;
    }
  });

  const [isFlipped, setIsFlipped] = useState(false);
  
  const toggleFlip = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsFlipped(!isFlipped);
  };

  // Calculate hover effects for parent-child relationships
  const getRelatedTaskIds = () => {
    const relatedIds = new Set<string>();
    
    if (task.parent_task_id) {
      // If this is a subtask, include parent
      relatedIds.add(task.parent_task_id);
    } else {
      // If this is a parent task, include all subtasks
      const subtasks = allTasks.filter(t => t.parent_task_id === task.id);
      subtasks.forEach(subtask => relatedIds.add(subtask.id));
    }
    
    return relatedIds;
  };

  const relatedTaskIds = getRelatedTaskIds();
  const isHighlighted = hoveredTaskId ? relatedTaskIds.has(hoveredTaskId) || hoveredTaskId === task.id : false;

  const handleMouseEnter = () => {
    onTaskHover?.(task.id);
  };

  const handleMouseLeave = () => {
    onTaskHover?.(null);
  };

  // Get subtasks for this parent task
  const subtasks = allTasks.filter(t => t.parent_task_id === task.id);
  
  // Card styling - using CSS-based height animation for better scrolling
  
  // Card styling constants
  const cardScale = 'scale-100';
  const cardOpacity = 'opacity-100';
  
  // Subtle highlight effect for related tasks
  const highlightGlow = isHighlighted 
    ? 'ring-1 ring-cyan-400/50' 
    : '';
    
  // Subtle hover effect with soft border glow (combining border color and shadow for glow)
  const hoverEffectClasses = 'group-hover:border-cyan-300/70 dark:group-hover:border-cyan-500/40 group-hover:shadow-[0_0_12px_rgba(34,211,238,0.3)] dark:group-hover:shadow-[0_0_12px_rgba(34,211,238,0.5)]';
  
  // Base card styles with proper rounded corners
  const cardBaseStyles = 'bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border border-gray-200 dark:border-gray-700 rounded-lg';
  
  // Transition settings
  const transitionStyles = 'transition-all duration-200 ease-in-out';

  return (
    <div 
      ref={(node) => drag(drop(node))}
      style={{ 
        perspective: '1000px',
        transformStyle: 'preserve-3d'
      }}
      className={`flip-card w-full cursor-move relative ${cardScale} ${cardOpacity} ${isDragging ? 'opacity-50 scale-90' : ''} ${transitionStyles} ${showSubtasks && subtasks.length > 0 ? 'card-expanded' : 'card-collapsed'} group ${highlightGlow}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div 
        className={`relative w-full h-full transform-style-preserve-3d ${isFlipped ? 'rotate-y-180' : ''}`}
      >
        {/* Front side with subtle hover effect */}
        <div className={`absolute w-full h-full backface-hidden ${cardBaseStyles} ${transitionStyles} ${hoverEffectClasses} rounded-lg`}>
          {/* Priority indicator */}
          <div className={`absolute left-0 top-0 bottom-0 w-[3px] ${getOrderColor(task.task_order)} ${getOrderGlow(task.task_order)} rounded-l-lg opacity-80 group-hover:w-[4px] group-hover:opacity-100 transition-all duration-300`}></div>
          
          {/* Content container with fixed padding - exactly matching back side structure */}
          <div className="flex flex-col h-full p-3">
            <div className="flex items-center gap-2 mb-2 pl-1.5">
              <div className="px-2 py-1 rounded-md text-xs font-medium flex items-center gap-1 backdrop-blur-md" 
                   style={{
                     backgroundColor: `${task.featureColor}20`,
                     color: task.featureColor,
                     boxShadow: `0 0 10px ${task.featureColor}20`
                   }}
              >
                <Tag className="w-3 h-3" />
                {task.feature}
              </div>
              
              {/* Task order display */}
              <div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold text-white ${getOrderColor(task.task_order)}`}>
                {task.task_order}
              </div>
              
              {/* Action buttons group */}
              <div className="ml-auto flex items-center gap-1.5">
                <button 
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(task);
                  }} 
                  className="w-5 h-5 rounded-full flex items-center justify-center bg-red-100/80 dark:bg-red-500/20 text-red-600 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-500/30 hover:shadow-[0_0_10px_rgba(239,68,68,0.3)] transition-all duration-300"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
                <button 
                  onClick={(e) => {
                    e.stopPropagation();
                    onView();
                  }} 
                  className="w-5 h-5 rounded-full flex items-center justify-center bg-cyan-100/80 dark:bg-cyan-500/20 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-200 dark:hover:bg-cyan-500/30 hover:shadow-[0_0_10px_rgba(34,211,238,0.3)] transition-all duration-300"
                >
                  <Edit className="w-3 h-3" />
                </button>
                <button 
                  onClick={toggleFlip} 
                  className="w-5 h-5 rounded-full flex items-center justify-center bg-cyan-100/80 dark:bg-cyan-500/20 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-200 dark:hover:bg-cyan-500/30 hover:shadow-[0_0_10px_rgba(34,211,238,0.3)] transition-all duration-300"
                >
                  <RefreshCw className="w-3 h-3" />
                </button>
              </div>
            </div>
            
            <h4 className="font-medium text-gray-900 dark:text-white mb-2 pl-1.5 line-clamp-2 overflow-hidden" title={task.title}>
              {task.title}
            </h4>
            
            {/* Subtasks display - exactly matching back side pattern for scrolling */}
            <div className="flex-1 overflow-hidden relative" style={{ display: showSubtasks ? 'block' : 'none' }}>
              <div className="absolute inset-0 overflow-y-auto hide-scrollbar pl-1.5 pr-2">
                <div className={`pt-1 border-l-2 border-cyan-200/30 dark:border-cyan-800/30 pr-1 space-y-1 ${!showSubtasks ? 'opacity-0' : 'opacity-100'}`}>
                  {subtasks.map((subtask, index) => (
                    <div 
                      key={subtask.id} 
                      className={`flex items-start gap-2 text-xs bg-gray-100/50 dark:bg-gray-800/50 rounded px-2 py-1 transform transition-all duration-300 ease-in-out hover:bg-gray-200/50 dark:hover:bg-gray-700/50 hover:shadow-sm cursor-pointer relative ${
                        showSubtasks 
                          ? 'translate-y-0 opacity-100' 
                          : '-translate-y-2 opacity-0'
                      }`}
                      style={{ 
                        transitionDelay: showSubtasks ? `${index * 50}ms` : '0ms'
                      }}
                      onClick={(e) => handleSubtaskClick(subtask.id, e)}
                    >
                      <span className={`flex-1 text-gray-600 dark:text-gray-400 text-[11px] ${
                        expandedSubtask === subtask.id ? 'whitespace-normal break-words' : 'truncate'
                      }`}>
                        {subtask.title}
                      </span>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold transition-all duration-200 flex-shrink-0 ${
                        subtask.status === 'complete' ? 'bg-green-200 text-green-800 dark:bg-green-900 dark:text-green-200' :
                        subtask.status === 'in-progress' ? 'bg-blue-200 text-blue-800 dark:bg-blue-900 dark:text-blue-200' :
                        subtask.status === 'review' ? 'bg-purple-200 text-purple-800 dark:bg-purple-900 dark:text-purple-200' :
                        'bg-gray-200 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                      }`}>
                        {subtask.status === 'backlog' ? 'Backlog' :
                         subtask.status === 'in-progress' ? 'In Progress' :
                         subtask.status === 'review' ? 'Review' : 'Complete'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            
            <div className="flex items-center justify-between mt-auto pt-2 pl-1.5 pr-3">
              <div className="flex items-center gap-2">
                <div className="flex items-center justify-center w-5 h-5 rounded-full bg-white/80 dark:bg-black/70 border border-gray-300/50 dark:border-gray-700/50 backdrop-blur-md" 
                     style={{boxShadow: getAssigneeGlow(task.assignee?.name || 'User')}}
                >
                  {getAssigneeIcon(task.assignee?.name || 'User')}
                </div>
                <span className="text-gray-600 dark:text-gray-400 text-xs">{task.assignee?.name || 'User'}</span>
              </div>
              <button 
                onClick={(e) => {
                  e.stopPropagation();
                  navigator.clipboard.writeText(task.id);
                  // Optional: Add a small toast or visual feedback here
                  const button = e.currentTarget;
                  const originalHTML = button.innerHTML;
                  button.innerHTML = '<span class="text-green-500">Copied!</span>';
                  setTimeout(() => {
                    button.innerHTML = originalHTML;
                  }, 2000);
                }}
                className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
                title="Copy Task ID to clipboard"
              >
                <Clipboard className="w-3 h-3" />
                <span>Task ID</span>
              </button>
            </div>
          </div>
        </div>
        
        {/* Back side */}
        {/* Back side with same hover effect */}
        <div className={`absolute w-full h-full backface-hidden ${cardBaseStyles} ${transitionStyles} ${hoverEffectClasses} rounded-lg rotate-y-180 ${isDragging ? 'opacity-0' : 'opacity-100'}`}>
          {/* Priority indicator */}
          <div className={`absolute left-0 top-0 bottom-0 w-[3px] ${getOrderColor(task.task_order)} ${getOrderGlow(task.task_order)} rounded-l-lg opacity-80 group-hover:w-[4px] group-hover:opacity-100 transition-all duration-300`}></div>
          
          {/* Content container with fixed padding */}
          <div className="flex flex-col h-full p-3">
            <div className="flex items-center gap-2 mb-2 pl-1.5">
              <h4 className="font-medium text-gray-900 dark:text-white truncate max-w-[75%]">
                {task.title}
              </h4>
              <button 
                onClick={toggleFlip} 
                className="ml-auto w-5 h-5 rounded-full flex items-center justify-center bg-cyan-100/80 dark:bg-cyan-500/20 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-200 dark:hover:bg-cyan-500/30 hover:shadow-[0_0_10px_rgba(34,211,238,0.3)] transition-all duration-300"
              >
                <RefreshCw className="w-3 h-3" />
              </button>
            </div>
            
            {/* Description container with absolute positioning inside parent bounds */}
            <div className="flex-1 overflow-hidden relative">
              <div className="absolute inset-0 overflow-y-auto hide-scrollbar pl-1.5 pr-2">
                <p className="text-xs text-gray-700 dark:text-gray-300 break-words whitespace-pre-wrap">{task.description}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}; 