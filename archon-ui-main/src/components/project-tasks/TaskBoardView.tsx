import React, { useRef, useState } from 'react';
import { useDrag, useDrop } from 'react-dnd';
import { Edit, Trash2, RefreshCw, Tag, User, Bot, Clipboard } from 'lucide-react';

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
}

interface TaskBoardViewProps {
  tasks: Task[];
  onTaskView: (task: Task) => void;
  onTaskComplete: (taskId: string) => void;
  onTaskDelete: (taskId: string) => void;
  onTaskMove: (taskId: string, newStatus: Task['status']) => void;
  onTaskReorder: (taskId: string, newOrder: number, status: Task['status']) => void;
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
}

const DraggableTaskCard = ({
  task,
  index,
  onView,
  onComplete,
  onDelete,
  onTaskReorder,
  tasksInStatus
}: DraggableTaskCardProps) => {
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

  return (
    <div 
      ref={(node) => drag(drop(node))}
      className={`flip-card h-[140px] w-full cursor-move ${isDragging ? 'opacity-50 scale-95' : 'opacity-100'} transition-all duration-300`} 
      style={{ perspective: '1000px' }}
    >
      <div className={`relative w-full h-full transition-transform duration-500 transform-style-preserve-3d ${isFlipped ? 'rotate-y-180' : ''}`}>
        {/* Front side */}
        <div className="absolute w-full h-full backface-hidden bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border border-gray-200 dark:border-gray-800 rounded-lg p-3 hover:border-gray-300 dark:hover:border-gray-700 transition-all duration-300 group shadow-[0_10px_30px_-15px_rgba(0,0,0,0.1)] dark:shadow-[0_10px_30px_-15px_rgba(0,0,0,0.7)]">
          {/* Priority indicator */}
          <div className={`absolute left-0 top-0 bottom-0 w-[3px] ${getOrderColor(task.task_order)} ${getOrderGlow(task.task_order)} rounded-l-lg opacity-80 group-hover:w-[4px] group-hover:opacity-100 transition-all duration-300`}></div>
          
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
          
          <div className="flex items-center justify-between absolute bottom-3 left-3 right-3 pl-1.5">
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
        <div className="absolute w-full h-full backface-hidden bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border border-gray-200 dark:border-gray-800 rounded-lg p-3 rotate-y-180 transition-all duration-300 group shadow-[0_10px_30px_-15px_rgba(0,0,0,0.1)] dark:shadow-[0_10px_30px_-15px_rgba(0,0,0,0.7)]">
          {/* Priority indicator */}
          <div className={`absolute left-0 top-0 bottom-0 w-[3px] ${getOrderColor(task.task_order)} ${getOrderGlow(task.task_order)} rounded-l-lg opacity-80 group-hover:w-[4px] group-hover:opacity-100 transition-all duration-300`}></div>
          
          <div className="flex items-center gap-2 mb-2 pl-1.5">
            <h4 className="font-medium text-gray-900 dark:text-white">
              {task.title}
            </h4>
            <button 
              onClick={toggleFlip} 
              className="ml-auto w-5 h-5 rounded-full flex items-center justify-center bg-cyan-100/80 dark:bg-cyan-500/20 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-200 dark:hover:bg-cyan-500/30 hover:shadow-[0_0_10px_rgba(34,211,238,0.3)] transition-all duration-300"
            >
              <RefreshCw className="w-3 h-3" />
            </button>
          </div>
          
          <div className="h-[75px] overflow-y-auto text-gray-700 dark:text-gray-300 text-xs mb-2 scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-700 scrollbar-track-transparent pr-1 pl-1.5">
            <p>{task.description}</p>
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
}

const ColumnDropZone = ({
  status,
  title,
  tasks,
  onTaskMove,
  onTaskView,
  onTaskComplete,
  onTaskDelete,
  onTaskReorder
}: ColumnDropZoneProps) => {
  const ref = useRef<HTMLDivElement>(null);
  
  const [{ isOver }, drop] = useDrop({
    accept: ItemTypes.TASK,
    drop: (item: { id: string; status: string }) => {
      if (item.status !== status) {
        // Moving to different status - calculate new order
        const newOrder = tasks.length + 1;
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

  // Sort tasks by task_order
  const sortedTasks = [...tasks].sort((a, b) => a.task_order - b.task_order);

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
        {sortedTasks.map((task, index) => (
          <DraggableTaskCard
            key={task.id}
            task={task}
            index={index}
            onView={() => onTaskView(task)}
            onComplete={() => onTaskComplete(task.id)}
            onDelete={() => onTaskDelete(task.id)}
            onTaskReorder={onTaskReorder}
            tasksInStatus={sortedTasks}
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
  onTaskReorder
}: TaskBoardViewProps) => {
  // Group tasks by status
  const getTasksByStatus = (status: Task['status']) => {
    return tasks.filter(task => task.status === status);
  };

  return (
    <div className="grid grid-cols-4 gap-0 h-full min-h-[70vh]">
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
      />
    </div>
  );
}; 