import React, { useRef, useState, useEffect, useCallback } from 'react';
import { useDrag, useDrop } from 'react-dnd';
import { Edit, Trash2, RefreshCw, Tag, User, Bot, Clipboard, List } from 'lucide-react';
import { Toggle } from '../ui/Toggle';

export interface Task {
  id: string;
  title: string;
  description: string;
  status: 'backlog' | 'in-progress' | 'review' | 'complete';
  assignee: {
    name: 'User' | 'Archon' | 'AI IDE Agent';
    avatar: string;
  };
  feature: string;
  featureColor: string;
  task_order: number;
  parent_task_id?: string; // Added for subtask support
}

interface TaskBoardViewProps {
  tasks: Task[];
  onTaskView: (task: Task) => void;
  onTaskComplete: (taskId: string) => void;
  onTaskDelete: (taskId: string) => void;
  onTaskMove: (taskId: string, newStatus: Task['status']) => void;
  onTaskReorder: (taskId: string, newOrder: number, status: Task['status']) => void;
  showSubtasks?: boolean;
  showSubtasksToggle?: boolean;
  onShowSubtasksChange?: (show: boolean) => void;
}

const ItemTypes = {
  TASK: 'task'
};

const getAssigneeIcon = (assigneeName: 'User' | 'Archon' | 'AI IDE Agent') => {
  switch (assigneeName) {
    case 'User':
      return <User className="w-4 h-4 text-blue-400" />;
    case 'AI IDE Agent':
      return <Bot className="w-4 h-4 text-purple-400" />;
    case 'Archon':
      return <img src="/logo-neon.svg" alt="Archon" className="w-4 h-4" />;
    default:
      return <User className="w-4 h-4 text-blue-400" />;
  }
};

const getAssigneeGlow = (assigneeName: 'User' | 'Archon' | 'AI IDE Agent') => {
  switch (assigneeName) {
    case 'User':
      return 'shadow-[0_0_10px_rgba(59,130,246,0.4)]';
    case 'AI IDE Agent':
      return 'shadow-[0_0_10px_rgba(168,85,247,0.4)]';
    case 'Archon':
      return 'shadow-[0_0_10px_rgba(34,211,238,0.4)]';
    default:
      return 'shadow-[0_0_10px_rgba(59,130,246,0.4)]';
  }
};

// Get color based on task order (lower = higher priority = warmer color)
const getOrderColor = (order: number) => {
  if (order <= 3) return 'bg-rose-500';
  if (order <= 6) return 'bg-orange-500';
  if (order <= 10) return 'bg-blue-500';
  return 'bg-emerald-500';
};

const getOrderGlow = (order: number) => {
  if (order <= 3) return 'shadow-[0_0_10px_rgba(244,63,94,0.7)]';
  if (order <= 6) return 'shadow-[0_0_10px_rgba(249,115,22,0.7)]';
  if (order <= 10) return 'shadow-[0_0_10px_rgba(59,130,246,0.7)]';
  return 'shadow-[0_0_10px_rgba(16,185,129,0.7)]';
};

interface DraggableTaskCardProps {
  task: Task;
  index: number;
  onView: () => void;
  onComplete: () => void;
  onDelete: () => void;
  onTaskReorder: (taskId: string, newOrder: number, status: Task['status']) => void;
  tasksInStatus: Task[];
  allTasks?: Task[];
  hoveredTaskId?: string | null;
  onTaskHover?: (taskId: string | null) => void;
  showSubtasks?: boolean;
}

const DraggableTaskCard = ({
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
  
  // Card styling - dynamic height with better subtask expansion
  const baseHeight = 140;
  const maxSubtaskAreaHeight = 240; // Increased from 128px to accommodate more subtasks
  const expandedHeight = showSubtasks && subtasks.length > 0 
    ? baseHeight + maxSubtaskAreaHeight + 16 // +16 for padding
    : baseHeight;
  
  const cardScale = 'scale-100';
  const cardOpacity = 'opacity-100';
  const highlightGlow = isHighlighted ? 'shadow-[0_0_20px_rgba(34,211,238,0.6)] ring-2 ring-cyan-400/50' : '';
  const hoverGlow = 'hover:shadow-[0_0_15px_rgba(34,211,238,0.4)] hover:ring-1 hover:ring-cyan-400/30';

  return (
    <div 
      ref={(node) => drag(drop(node))}
      className={`flip-card w-full cursor-move ${cardScale} ${cardOpacity} ${isDragging ? 'opacity-50 scale-90' : ''} transition-all duration-500 ease-in-out ${highlightGlow} ${hoverGlow}`} 
      style={{ 
        perspective: '1000px',
        height: `${expandedHeight}px`,
        transition: 'height 0.5s ease-in-out'
      }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div 
        className={`relative w-full h-full transition-transform duration-500 transform-style-preserve-3d ${isFlipped ? 'rotate-y-180' : ''}`}
      >
        {/* Front side */}
        <div className="absolute w-full h-full backface-hidden bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border border-gray-200 dark:border-gray-800 rounded-lg p-3 hover:border-gray-300 dark:hover:border-gray-700 transition-all duration-300 group shadow-[0_10px_30px_-15px_rgba(0,0,0,0.1)] dark:shadow-[0_10px_30px_-15px_rgba(0,0,0,0.7)] flex flex-col">
          {/* Priority indicator */}
          <div className={`absolute left-0 top-0 bottom-0 w-[3px] ${getOrderColor(task.task_order)} ${getOrderGlow(task.task_order)} rounded-l-lg opacity-80 group-hover:w-[4px] group-hover:opacity-100 transition-all duration-300`}></div>
          
          <div className="flex items-center gap-2 mb-2 pl-1.5">
            {/* No subtask indicator needed since these are all parent tasks */}
            
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
                  onDelete();
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
          
          {/* Subtasks display with smooth animations and scrolling */}
          <div className={`overflow-hidden transition-all duration-500 ease-in-out ${
            showSubtasks && subtasks.length > 0 
              ? 'max-h-60 opacity-100' 
              : 'max-h-0 opacity-0'
          }`}>
            <div className="pl-1.5 mb-2 pt-1 max-h-60 overflow-y-auto scrollbar scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600 scrollbar-track-gray-100/50 dark:scrollbar-track-gray-800/50 hover:scrollbar-thumb-gray-400 dark:hover:scrollbar-thumb-gray-500 pr-1 border-l-2 border-cyan-200/30 dark:border-cyan-800/30">
              <div className="space-y-1">
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
        
        {/* Back side */}
        <div className={`absolute w-full h-full backface-hidden bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border border-gray-200 dark:border-gray-800 rounded-lg rotate-y-180 transition-all duration-300 group shadow-[0_10px_30px_-15px_rgba(0,0,0,0.1)] dark:shadow-[0_10px_30px_-15px_rgba(0,0,0,0.7)] ${isDragging ? 'opacity-0' : 'opacity-100'}`}>
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

interface ColumnDropZoneProps {
  status: Task['status'];
  title: string;
  tasks: Task[];
  onTaskMove: (taskId: string, newStatus: Task['status']) => void;
  onTaskView: (task: Task) => void;
  onTaskComplete: (taskId: string) => void;
  onTaskDelete: (taskId: string) => void;
  onTaskReorder: (taskId: string, newOrder: number, status: Task['status']) => void;
  allTasks: Task[];
  showSubtasks: boolean;
  hoveredTaskId: string | null;
  onTaskHover: (taskId: string | null) => void;
}

const ColumnDropZone = ({
  status,
  title,
  tasks,
  onTaskMove,
  onTaskView,
  onTaskComplete,
  onTaskDelete,
  onTaskReorder,
  allTasks,
  showSubtasks,
  hoveredTaskId,
  onTaskHover
}: ColumnDropZoneProps) => {
  const ref = useRef<HTMLDivElement>(null);
  
  const [{ isOver }, drop] = useDrop({
    accept: ItemTypes.TASK,
    drop: (item: { id: string; status: string }) => {
      if (item.status !== status) {
        // Moving to different status - use length of current column as new order
        onTaskMove(item.id, status);
      }
    },
    collect: (monitor) => ({
      isOver: !!monitor.isOver()
    })
  });

  drop(ref);

  // Get column header color based on status
  const getColumnColor = () => {
    switch (status) {
      case 'backlog':
        return 'text-gray-600 dark:text-gray-400';
      case 'in-progress':
        return 'text-blue-600 dark:text-blue-400';
      case 'review':
        return 'text-purple-600 dark:text-purple-400';
      case 'complete':
        return 'text-green-600 dark:text-green-400';
    }
  };

  // Get column header glow based on status
  const getColumnGlow = () => {
    switch (status) {
      case 'backlog':
        return 'bg-gray-500/30';
      case 'in-progress':
        return 'bg-blue-500/30 shadow-[0_0_10px_2px_rgba(59,130,246,0.2)]';
      case 'review':
        return 'bg-purple-500/30 shadow-[0_0_10px_2px_rgba(168,85,247,0.2)]';
      case 'complete':
        return 'bg-green-500/30 shadow-[0_0_10px_2px_rgba(16,185,129,0.2)]';
    }
  };

  // Just use the tasks as-is since they're already parent tasks only
  const organizedTasks = tasks;

  return (
    <div 
      ref={ref} 
      className={`flex flex-col bg-white/20 dark:bg-black/30 ${isOver ? 'bg-gray-100/50 dark:bg-gray-800/20 border-t-2 border-t-[#00ff00] shadow-[inset_0_1px_10px_rgba(0,255,0,0.1)]' : ''} transition-colors duration-200 h-full`}
    >
      <div className="text-center py-3 relative sticky top-0 z-10 bg-white/80 dark:bg-black/80 backdrop-blur-sm">
        <h3 className={`font-mono ${getColumnColor()} text-sm`}>{title}</h3>
        {/* Column header divider with glow */}
        <div className={`absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[1px] ${getColumnGlow()}`}></div>
      </div>
      
      <div className="px-1 flex-1 overflow-y-auto space-y-3 py-3">
        {organizedTasks.map((task, index) => (
          <DraggableTaskCard
            key={task.id}
            task={task}
            index={index}
            onView={() => onTaskView(task)}
            onComplete={() => onTaskComplete(task.id)}
            onDelete={() => onTaskDelete(task.id)}
            onTaskReorder={onTaskReorder}
            tasksInStatus={organizedTasks}
            allTasks={allTasks}
            hoveredTaskId={hoveredTaskId}
            onTaskHover={onTaskHover}
            showSubtasks={showSubtasks}
          />
        ))}
      </div>
    </div>
  );
};

export const TaskBoardView = ({
  tasks,
  onTaskView,
  onTaskComplete,
  onTaskDelete,
  onTaskMove,
  onTaskReorder,
  showSubtasks = false,
  showSubtasksToggle = false,
  onShowSubtasksChange
}: TaskBoardViewProps) => {
  const [hoveredTaskId, setHoveredTaskId] = useState<string | null>(null);

  // Simple task filtering for board view - only show parent tasks
  const getTasksByStatus = (status: Task['status']) => {
    // Always only show parent tasks in columns
    // Subtasks will be displayed inside parent cards when showSubtasks is true
    const parentTasks = tasks
      .filter(task => task.status === status && !task.parent_task_id)
      .sort((a, b) => a.task_order - b.task_order);
    
    return parentTasks;
  };

  return (
    <div className="flex flex-col h-full min-h-[70vh]">
      {/* Show Subtasks Toggle */}
      {showSubtasksToggle && onShowSubtasksChange && (
        <div className="mb-4 flex justify-end">
          <div className="flex items-center gap-3 p-3 rounded-lg bg-gradient-to-r from-blue-500/5 to-blue-500/0">
            <div className="flex-1 min-w-0">
              <p className="font-medium text-gray-800 dark:text-white text-sm">
                Show Subtasks
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Display subtasks indented under parent tasks
              </p>
            </div>
            <div className="flex-shrink-0">
              <Toggle 
                checked={showSubtasks} 
                onCheckedChange={onShowSubtasksChange} 
                accentColor="blue" 
                icon={<List className="w-5 h-5" />} 
              />
            </div>
          </div>
        </div>
      )}

      {/* Board Columns */}
      <div className="grid grid-cols-4 gap-0 flex-1">
        {/* Backlog Column */}
        <ColumnDropZone
          status="backlog"
          title="Backlog"
          tasks={getTasksByStatus('backlog')}
          onTaskMove={onTaskMove}
          onTaskView={onTaskView}
          onTaskComplete={onTaskComplete}
          onTaskDelete={onTaskDelete}
          onTaskReorder={onTaskReorder}
          allTasks={tasks}
          showSubtasks={showSubtasks}
          hoveredTaskId={hoveredTaskId}
          onTaskHover={setHoveredTaskId}
        />
        
        {/* In Progress Column */}
        <ColumnDropZone
          status="in-progress"
          title="In Process"
          tasks={getTasksByStatus('in-progress')}
          onTaskMove={onTaskMove}
          onTaskView={onTaskView}
          onTaskComplete={onTaskComplete}
          onTaskDelete={onTaskDelete}
          onTaskReorder={onTaskReorder}
          allTasks={tasks}
          showSubtasks={showSubtasks}
          hoveredTaskId={hoveredTaskId}
          onTaskHover={setHoveredTaskId}
        />
        
        {/* Review Column */}
        <ColumnDropZone
          status="review"
          title="Review"
          tasks={getTasksByStatus('review')}
          onTaskMove={onTaskMove}
          onTaskView={onTaskView}
          onTaskComplete={onTaskComplete}
          onTaskDelete={onTaskDelete}
          onTaskReorder={onTaskReorder}
          allTasks={tasks}
          showSubtasks={showSubtasks}
          hoveredTaskId={hoveredTaskId}
          onTaskHover={setHoveredTaskId}
        />
        
        {/* Complete Column */}
        <ColumnDropZone
          status="complete"
          title="Complete"
          tasks={getTasksByStatus('complete')}
          onTaskMove={onTaskMove}
          onTaskView={onTaskView}
          onTaskComplete={onTaskComplete}
          onTaskDelete={onTaskDelete}
          onTaskReorder={onTaskReorder}
          allTasks={tasks}
          showSubtasks={showSubtasks}
          hoveredTaskId={hoveredTaskId}
          onTaskHover={setHoveredTaskId}
        />
      </div>
    </div>
  );
}; 