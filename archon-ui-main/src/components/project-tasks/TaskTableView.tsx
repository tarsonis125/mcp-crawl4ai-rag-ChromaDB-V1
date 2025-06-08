import React, { useState } from 'react';
import { useDrag, useDrop } from 'react-dnd';
import { Check, Trash2, Edit, Tag, User, Bot, Clipboard, X, Save, Plus } from 'lucide-react';

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

interface TaskTableViewProps {
  tasks: Task[];
  onTaskView: (task: Task) => void;
  onTaskComplete: (taskId: string) => void;
  onTaskDelete: (taskId: string) => void;
  onTaskReorder: (taskId: string, newOrder: number, status: Task['status']) => void;
  onTaskCreate?: (task: Omit<Task, 'id'>) => Promise<void>;
  onTaskUpdate?: (taskId: string, updates: Partial<Task>) => Promise<void>;
}

const ItemTypes = {
  TASK: 'task'
};

const getAssigneeIcon = (assigneeName: 'User' | 'Archon' | 'AI IDE Agent') => {
  switch (assigneeName) {
    case 'User':
      return <User className="w-4 h-4 text-blue-500 dark:text-blue-400" />;
    case 'AI IDE Agent':
      return <Bot className="w-4 h-4 text-emerald-500 dark:text-emerald-400" />;
    case 'Archon':
      return <img src="/logo-neon.svg" alt="Archon" className="w-4 h-4 text-pink-500 dark:text-pink-400" />;
    default:
      return <User className="w-4 h-4 text-blue-500 dark:text-blue-400" />;
  }
};

const getAssigneeGlow = (assigneeName: 'User' | 'Archon' | 'AI IDE Agent') => {
  switch (assigneeName) {
    case 'User':
      return 'shadow-[0_0_12px_rgba(59,130,246,0.6)] hover:shadow-[0_0_16px_rgba(59,130,246,0.8)]'; // blue glow
    case 'AI IDE Agent':
      return 'shadow-[0_0_12px_rgba(16,185,129,0.6)] hover:shadow-[0_0_16px_rgba(16,185,129,0.8)]'; // emerald green glow
    case 'Archon':
      return 'shadow-[0_0_12px_rgba(236,72,153,0.6)] hover:shadow-[0_0_16px_rgba(236,72,153,0.8)]'; // pink glow
    default:
      return 'shadow-[0_0_10px_rgba(59,130,246,0.5)]';
  }
};

const getAssigneeGlassStyle = (assigneeName: 'User' | 'Archon' | 'AI IDE Agent') => {
  switch (assigneeName) {
    case 'User':
      return 'backdrop-blur-md bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border-blue-400 dark:border-blue-500'; // blue glass
    case 'AI IDE Agent':
      return 'backdrop-blur-md bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border-emerald-400 dark:border-emerald-500'; // emerald green glass (like toggle)
    case 'Archon':
      return 'backdrop-blur-md bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border-pink-400 dark:border-pink-500'; // pink glass
    default:
      return 'backdrop-blur-md bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border-blue-400 dark:border-blue-500';
  }
};

// Get glass morphism style based on task order (lower = higher priority = warmer color)
const getOrderGlassStyle = (order: number) => {
  if (order <= 3) return 'backdrop-blur-md bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border-rose-400 dark:border-rose-500'; // red glass
  if (order <= 6) return 'backdrop-blur-md bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border-orange-400 dark:border-orange-500'; // orange glass
  if (order <= 10) return 'backdrop-blur-md bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border-blue-400 dark:border-blue-500'; // blue glass
  return 'backdrop-blur-md bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border-emerald-400 dark:border-emerald-500'; // green glass
};

const getOrderTextColor = (order: number) => {
  if (order <= 3) return 'text-rose-500 dark:text-rose-400'; // red text
  if (order <= 6) return 'text-orange-500 dark:text-orange-400'; // orange text
  if (order <= 10) return 'text-blue-500 dark:text-blue-400'; // blue text
  return 'text-emerald-500 dark:text-emerald-400'; // green text
};

const getOrderGlow = (order: number) => {
  if (order <= 3) return 'shadow-[0_0_12px_rgba(244,63,94,0.6)] hover:shadow-[0_0_16px_rgba(244,63,94,0.8)]'; // red glow
  if (order <= 6) return 'shadow-[0_0_12px_rgba(249,115,22,0.6)] hover:shadow-[0_0_16px_rgba(249,115,22,0.8)]'; // orange glow
  if (order <= 10) return 'shadow-[0_0_12px_rgba(59,130,246,0.6)] hover:shadow-[0_0_16px_rgba(59,130,246,0.8)]'; // blue glow
  return 'shadow-[0_0_12px_rgba(16,185,129,0.6)] hover:shadow-[0_0_16px_rgba(16,185,129,0.8)]'; // green glow
};

// Helper function to reorder tasks properly
const reorderTasks = (tasks: Task[], fromIndex: number, toIndex: number): Task[] => {
  const result = [...tasks];
  const [movedTask] = result.splice(fromIndex, 1);
  result.splice(toIndex, 0, movedTask);
  
  // Update task_order to be sequential (1, 2, 3, ...)
  return result.map((task, index) => ({
    ...task,
    task_order: index + 1
  }));
};

// Inline editable cell component
interface EditableCellProps {
  value: string;
  onSave: (value: string) => void;
  type?: 'text' | 'textarea' | 'select';
  options?: string[];
  placeholder?: string;
  isEditing: boolean;
  onEdit: () => void;
  onCancel: () => void;
}

const EditableCell = ({ 
  value, 
  onSave, 
  type = 'text', 
  options = [], 
  placeholder = '', 
  isEditing,
  onEdit,
  onCancel
}: EditableCellProps) => {
  const [editValue, setEditValue] = useState(value);

  const handleSave = () => {
    onSave(editValue);
  };

  const handleCancel = () => {
    setEditValue(value);
    onCancel();
  };

  if (!isEditing) {
    return (
      <div 
        onClick={onEdit}
        className="cursor-pointer hover:bg-gray-100/50 dark:hover:bg-gray-800/30 p-1 rounded transition-colors min-h-[24px] flex items-center truncate"
        title={value || placeholder}
      >
        <span className="truncate">
          {value || <span className="text-gray-400 italic">Click to edit</span>}
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {type === 'select' ? (
        <select
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          className="flex-1 bg-white/90 dark:bg-black/90 border border-cyan-300 dark:border-cyan-600 rounded px-2 py-1 text-sm focus:outline-none focus:border-cyan-500 focus:shadow-[0_0_5px_rgba(34,211,238,0.3)]"
          autoFocus
        >
          {options.map(option => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      ) : type === 'textarea' ? (
        <textarea
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          placeholder={placeholder}
          className="flex-1 bg-white/90 dark:bg-black/90 border border-cyan-300 dark:border-cyan-600 rounded px-2 py-1 text-sm focus:outline-none focus:border-cyan-500 focus:shadow-[0_0_5px_rgba(34,211,238,0.3)] resize-none"
          rows={2}
          autoFocus
        />
      ) : (
        <input
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          placeholder={placeholder}
          className="flex-1 bg-white/90 dark:bg-black/90 border border-cyan-300 dark:border-cyan-600 rounded px-2 py-1 text-sm focus:outline-none focus:border-cyan-500 focus:shadow-[0_0_5px_rgba(34,211,238,0.3)]"
          autoFocus
        />
      )}
      <button
        onClick={handleSave}
        className="p-1 rounded bg-green-500/20 text-green-600 hover:bg-green-500/30 transition-colors"
      >
        <Check className="w-3 h-3" />
      </button>
      <button
        onClick={handleCancel}
        className="p-1 rounded bg-red-500/20 text-red-600 hover:bg-red-500/30 transition-colors"
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  );
};

interface DraggableTaskRowProps {
  task: Task;
  index: number;
  onTaskView: (task: Task) => void;
  onTaskComplete: (taskId: string) => void;
  onTaskDelete: (taskId: string) => void;
  onTaskReorder: (taskId: string, newOrder: number, status: Task['status']) => void;
  onTaskUpdate?: (taskId: string, updates: Partial<Task>) => Promise<void>;
  tasksInStatus: Task[];
}

const DraggableTaskRow = ({ 
  task, 
  index, 
  onTaskView, 
  onTaskComplete, 
  onTaskDelete, 
  onTaskReorder,
  onTaskUpdate,
  tasksInStatus 
}: DraggableTaskRowProps) => {
  const [editingField, setEditingField] = useState<string | null>(null);
  const [isHovering, setIsHovering] = useState(false);
  
  const [{ isDragging }, drag] = useDrag({
    type: ItemTypes.TASK,
    item: { id: task.id, index, status: task.status },
    collect: (monitor) => ({
      isDragging: !!monitor.isDragging(),
    }),
  });

  const [{ isOver, canDrop }, drop] = useDrop({
    accept: ItemTypes.TASK,
    hover: (draggedItem: { id: string; index: number; status: Task['status'] }, monitor) => {
      if (!monitor.isOver({ shallow: true })) return;
      if (draggedItem.id === task.id) return;
      if (draggedItem.status !== task.status) return;
      
      const draggedIndex = draggedItem.index;
      const hoveredIndex = index;
      
      if (draggedIndex === hoveredIndex) return;
      
      console.log('HOVER: Moving task', draggedItem.id, 'from index', draggedIndex, 'to', hoveredIndex);
      
      // Move the task immediately for visual feedback
      onTaskReorder(draggedItem.id, hoveredIndex, task.status);
      
      // Update the dragged item's index to prevent re-triggering
      draggedItem.index = hoveredIndex;
    },
    collect: (monitor) => ({
      isOver: !!monitor.isOver(),
      canDrop: !!monitor.canDrop(),
    }),
  });

  const handleUpdateField = async (field: string, value: string) => {
    if (onTaskUpdate) {
      const updates: Partial<Task> = {};
      
      if (field === 'title') {
        updates.title = value;
      } else if (field === 'status') {
        updates.status = value as Task['status'];
      } else if (field === 'assignee') {
        updates.assignee = { name: value as 'User' | 'Archon' | 'AI IDE Agent', avatar: '' };
      } else if (field === 'feature') {
        updates.feature = value;
      }
      
      try {
        await onTaskUpdate(task.id, updates);
        setEditingField(null);
      } catch (error) {
        console.error('Failed to update task:', error);
      }
    }
  };

  return (
    <tr 
      ref={(node) => drag(drop(node))}
      className={`
        group transition-all duration-200 cursor-move
        ${index % 2 === 0 ? 'bg-white/50 dark:bg-black/50' : 'bg-gray-50/80 dark:bg-gray-900/30'}
        hover:bg-gradient-to-r hover:from-cyan-50/70 hover:to-purple-50/70 dark:hover:from-cyan-900/20 dark:hover:to-purple-900/20
        border-b border-gray-200 dark:border-gray-800 last:border-b-0
        ${isDragging ? 'opacity-50 scale-105 shadow-lg z-50' : ''}
        ${isOver && canDrop ? 'bg-cyan-100/50 dark:bg-cyan-900/20 border-cyan-400' : ''}
        ${isHovering ? 'transform translate-y-1 shadow-md' : ''}
      `}
      onMouseLeave={() => setIsHovering(false)}
    >
      <td className="p-3">
        <div className="flex items-center justify-center">
          <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center text-xs font-bold transition-all duration-300 ${getOrderGlassStyle(task.task_order)} ${getOrderTextColor(task.task_order)} ${getOrderGlow(task.task_order)}`}>
            {task.task_order}
          </div>
        </div>
      </td>
      <td className="p-3 text-gray-800 dark:text-gray-200 group-hover:text-gray-900 dark:group-hover:text-white transition-colors relative">
        <div className="min-w-0">
          <div className="truncate">
            <EditableCell
              value={task.title}
              onSave={(value) => handleUpdateField('title', value)}
              isEditing={editingField === 'title'}
              onEdit={() => setEditingField('title')}
              onCancel={() => setEditingField(null)}
              placeholder="Task title..."
            />
          </div>
        </div>
      </td>
      <td className="p-3">
        <EditableCell
          value={task.status === 'backlog' ? 'Backlog' : 
                task.status === 'in-progress' ? 'In Progress' : 
                task.status === 'review' ? 'Review' : 'Complete'}
          onSave={(value) => {
            const statusMap: Record<string, Task['status']> = {
              'Backlog': 'backlog',
              'In Progress': 'in-progress', 
              'Review': 'review',
              'Complete': 'complete'
            };
            handleUpdateField('status', statusMap[value] || 'backlog');
          }}
          type="select"
          options={['Backlog', 'In Progress', 'Review', 'Complete']}
          isEditing={editingField === 'status'}
          onEdit={() => setEditingField('status')}
          onCancel={() => setEditingField(null)}
        />
      </td>
      <td className="p-3">
        <div className="truncate">
          <EditableCell
            value={task.feature}
            onSave={(value) => handleUpdateField('feature', value)}
            isEditing={editingField === 'feature'}
            onEdit={() => setEditingField('feature')}
            onCancel={() => setEditingField(null)}
            placeholder="Feature name..."
          />
        </div>
      </td>
      <td className="p-3">
        <div className="flex items-center justify-center">
          <div 
            className={`flex items-center justify-center w-8 h-8 rounded-full border-2 transition-all duration-300 cursor-pointer hover:scale-110 ${getAssigneeGlassStyle(task.assignee?.name || 'User')} ${getAssigneeGlow(task.assignee?.name || 'User')}`}
            onClick={() => setEditingField('assignee')}
            title={`Assignee: ${task.assignee?.name || 'User'}`}
          >
            {getAssigneeIcon(task.assignee?.name || 'User')}
          </div>
          {editingField === 'assignee' && (
            <div className="absolute z-50 mt-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg shadow-lg p-2">
              <select
                value={task.assignee?.name || 'User'}
                onChange={(e) => {
                  handleUpdateField('assignee', e.target.value);
                  setEditingField(null);
                }}
                className="bg-white/90 dark:bg-black/90 border border-cyan-300 dark:border-cyan-600 rounded px-2 py-1 text-sm focus:outline-none focus:border-cyan-500"
                autoFocus
              >
                <option value="User">User</option>
                <option value="Archon">Archon</option>
                <option value="AI IDE Agent">AI IDE Agent</option>
              </select>
            </div>
          )}
        </div>
      </td>
      <td className="p-3">
        <div className="flex justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button 
            onClick={() => onTaskDelete(task.id)} 
            className="p-1.5 rounded-full bg-red-500/20 text-red-500 hover:bg-red-500/30 hover:shadow-[0_0_10px_rgba(239,68,68,0.3)] transition-all duration-300"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
          <button 
            onClick={() => onTaskComplete(task.id)} 
            className="p-1.5 rounded-full bg-green-500/20 text-green-500 hover:bg-green-500/30 hover:shadow-[0_0_10px_rgba(34,197,94,0.3)] transition-all duration-300"
          >
            <Check className="w-3.5 h-3.5" />
          </button>
          <button 
            onClick={() => onTaskView(task)} 
            className="p-1.5 rounded-full bg-cyan-500/20 text-cyan-500 hover:bg-cyan-500/30 hover:shadow-[0_0_10px_rgba(34,211,238,0.3)] transition-all duration-300"
          >
            <Edit className="w-3.5 h-3.5" />
          </button>
          {/* Copy Task ID Button - Matching Board View */}
          <button 
            onClick={(e) => {
              e.stopPropagation();
              navigator.clipboard.writeText(task.id);
              // Visual feedback like in board view
              const button = e.currentTarget;
              const originalHTML = button.innerHTML;
              button.innerHTML = '<div class="flex items-center gap-1"><span class="w-3 h-3 text-green-500">✓</span><span class="text-green-500 text-xs">Copied</span></div>';
              setTimeout(() => {
                button.innerHTML = originalHTML;
              }, 2000);
            }}
            className="p-1.5 rounded-full bg-gray-500/20 text-gray-500 hover:bg-gray-500/30 hover:shadow-[0_0_10px_rgba(107,114,128,0.3)] transition-all duration-300"
            title="Copy Task ID to clipboard"
          >
            <Clipboard className="w-3.5 h-3.5" />
          </button>
        </div>
      </td>
    </tr>
  );
};

// Add Task Row Component - Always visible empty input row
interface AddTaskRowProps {
  onTaskCreate?: (task: Omit<Task, 'id'>) => Promise<void>;
  tasks: Task[];
  statusFilter: Task['status'] | 'all';
}

const AddTaskRow = ({ onTaskCreate, tasks, statusFilter }: AddTaskRowProps) => {
  const [newTask, setNewTask] = useState<Omit<Task, 'id'>>({
    title: '',
    description: '',
    status: statusFilter === 'all' ? 'backlog' : statusFilter,
    assignee: { name: 'AI IDE Agent', avatar: '' },
    feature: '',
    featureColor: '#3b82f6',
    task_order: 1
  });

  const handleCreateTask = async () => {
    if (!newTask.title.trim() || !onTaskCreate) return;
    
    // Calculate the next order number for the target status
    const targetStatus = newTask.status;
    const tasksInStatus = tasks.filter(t => t.status === targetStatus);
    const nextOrder = tasksInStatus.length > 0 ? Math.max(...tasksInStatus.map(t => t.task_order)) + 1 : 1;
    
    try {
      await onTaskCreate({
        ...newTask,
        task_order: nextOrder
      });
      
      // Reset only the title to allow quick adding
      setNewTask(prev => ({
        ...prev,
        title: '',
        description: ''
      }));
    } catch (error) {
      console.error('Failed to create task:', error);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleCreateTask();
    }
  };

  // Update status when filter changes
  React.useEffect(() => {
    if (statusFilter !== 'all') {
      setNewTask(prev => ({ ...prev, status: statusFilter }));
    }
  }, [statusFilter]);

  return (
    <>
      <tr className="border-t border-cyan-400 dark:border-cyan-500 bg-cyan-50/30 dark:bg-cyan-900/10 relative">
        {/* Toned down neon blue line separator */}
        <td colSpan={6} className="p-0 relative">
          <div className="absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-transparent via-cyan-400 to-transparent shadow-[0_0_4px_1px_rgba(34,211,238,0.4)] dark:shadow-[0_0_6px_2px_rgba(34,211,238,0.5)]"></div>
        </td>
      </tr>
      <tr className="bg-cyan-50/20 dark:bg-cyan-900/5">
      <td className="p-3">
        <div className="flex items-center justify-center">
          <div className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white bg-cyan-500 shadow-[0_0_10px_rgba(34,211,238,0.5)]">
            +
          </div>
        </div>
      </td>
      <td className="p-3">
        <input
          type="text"
          value={newTask.title}
          onChange={(e) => setNewTask(prev => ({ ...prev, title: e.target.value }))}
          onKeyPress={handleKeyPress}
          placeholder="Type task title and press Enter..."
          className="w-full bg-white/90 dark:bg-black/90 border border-cyan-300 dark:border-cyan-600 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-cyan-500 focus:shadow-[0_0_5px_rgba(34,211,238,0.3)] transition-all duration-200"
          autoFocus
        />
      </td>
      <td className="p-3">
        <select
          value={newTask.status === 'backlog' ? 'Backlog' : 
                newTask.status === 'in-progress' ? 'In Progress' : 
                newTask.status === 'review' ? 'Review' : 'Complete'}
          onChange={(e) => {
            const statusMap: Record<string, Task['status']> = {
              'Backlog': 'backlog',
              'In Progress': 'in-progress', 
              'Review': 'review',
              'Complete': 'complete'
            };
            setNewTask(prev => ({ ...prev, status: statusMap[e.target.value] || 'backlog' }));
          }}
          className="w-full bg-white/90 dark:bg-black/90 border border-cyan-300 dark:border-cyan-600 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-cyan-500 focus:shadow-[0_0_5px_rgba(34,211,238,0.3)]"
        >
          <option value="Backlog">Backlog</option>
          <option value="In Progress">In Progress</option>
          <option value="Review">Review</option>
          <option value="Complete">Complete</option>
        </select>
      </td>
      <td className="p-3">
        <input
          type="text"
          value={newTask.feature}
          onChange={(e) => setNewTask(prev => ({ ...prev, feature: e.target.value }))}
          onKeyPress={handleKeyPress}
          placeholder="Feature..."
          className="w-full bg-white/90 dark:bg-black/90 border border-cyan-300 dark:border-cyan-600 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-cyan-500 focus:shadow-[0_0_5px_rgba(34,211,238,0.3)]"
        />
      </td>
      <td className="p-3">
        <select
          value={newTask.assignee.name}
          onChange={(e) => setNewTask(prev => ({ 
            ...prev, 
            assignee: { name: e.target.value as 'User' | 'Archon' | 'AI IDE Agent', avatar: '' }
          }))}
          className="w-full bg-white/90 dark:bg-black/90 border border-cyan-300 dark:border-cyan-600 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-cyan-500 focus:shadow-[0_0_5px_rgba(34,211,238,0.3)]"
        >
          <option value="AI IDE Agent">AI IDE Agent</option>
          <option value="User">User</option>
          <option value="Archon">Archon</option>
        </select>
      </td>
      <td className="p-3">
        <div className="flex justify-center">
          <span className="text-xs text-cyan-600 dark:text-cyan-400 font-medium">Press Enter</span>
        </div>
      </td>
    </tr>
    </>
  );
};

export const TaskTableView = ({ 
  tasks, 
  onTaskView, 
  onTaskComplete, 
  onTaskDelete, 
  onTaskReorder,
  onTaskCreate,
  onTaskUpdate
}: TaskTableViewProps) => {
  const [statusFilter, setStatusFilter] = useState<Task['status'] | 'all'>('backlog');

  // Group tasks by status and sort by task_order
  const getTasksByStatus = (status: Task['status']) => {
    return tasks
      .filter(task => task.status === status)
      .sort((a, b) => a.task_order - b.task_order);
  };

  const filteredTasks = statusFilter === 'all' ? tasks : tasks.filter(task => task.status === statusFilter);
  const statuses: Task['status'][] = ['backlog', 'in-progress', 'review', 'complete'];

  // Get column header color and glow based on header type (matching board view style)
  const getHeaderColor = (type: 'primary' | 'secondary') => {
    return type === 'primary' ? 'text-cyan-600 dark:text-cyan-400' : 'text-purple-600 dark:text-purple-400';
  };

  const getHeaderGlow = (type: 'primary' | 'secondary') => {
    return type === 'primary' ? 'bg-cyan-500 shadow-[0_0_8px_rgba(34,211,238,0.6)]' : 'bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.6)]';
  };

  return (
    <div className="overflow-x-auto">
      {/* Status Filter */}
      <div className="mb-4 flex gap-2 flex-wrap py-2">
        <button
          onClick={() => setStatusFilter('all')}
          className={`
            px-3 py-1.5 rounded-full text-xs transition-all duration-200
            ${statusFilter === 'all' 
              ? 'bg-cyan-100 dark:bg-cyan-900/20 text-cyan-600 dark:text-cyan-400 ring-1 ring-cyan-500/50 shadow-[0_0_8px_rgba(34,211,238,0.3)]' 
              : 'bg-gray-100/70 dark:bg-gray-800/50 text-gray-600 dark:text-gray-400 hover:bg-gray-200/70 dark:hover:bg-gray-700/50'
            }
          `}
        >
          All Tasks
        </button>
        {statuses.map((status) => {
          // Define colors for each status
          const getStatusColors = (status: Task['status']) => {
            switch (status) {
              case 'backlog':
                return {
                  selected: 'bg-gray-100 dark:bg-gray-900/20 text-gray-600 dark:text-gray-400 ring-1 ring-gray-500/50 shadow-[0_0_8px_rgba(107,114,128,0.3)]',
                  unselected: 'bg-gray-100/70 dark:bg-gray-800/50 text-gray-600 dark:text-gray-400 hover:bg-gray-200/70 dark:hover:bg-gray-700/50'
                };
              case 'in-progress':
                return {
                  selected: 'bg-blue-100 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 ring-1 ring-blue-500/50 shadow-[0_0_8px_rgba(59,130,246,0.3)]',
                  unselected: 'bg-gray-100/70 dark:bg-gray-800/50 text-gray-600 dark:text-gray-400 hover:bg-blue-200/30 dark:hover:bg-blue-900/20'
                };
              case 'review':
                return {
                  selected: 'bg-purple-100 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 ring-1 ring-purple-500/50 shadow-[0_0_8px_rgba(168,85,247,0.3)]',
                  unselected: 'bg-gray-100/70 dark:bg-gray-800/50 text-gray-600 dark:text-gray-400 hover:bg-purple-200/30 dark:hover:bg-purple-900/20'
                };
              case 'complete':
                return {
                  selected: 'bg-green-100 dark:bg-green-900/20 text-green-600 dark:text-green-400 ring-1 ring-green-500/50 shadow-[0_0_8px_rgba(34,197,94,0.3)]',
                  unselected: 'bg-gray-100/70 dark:bg-gray-800/50 text-gray-600 dark:text-gray-400 hover:bg-green-200/30 dark:hover:bg-green-900/20'
                };
              default:
                return {
                  selected: 'bg-gray-100 dark:bg-gray-900/20 text-gray-600 dark:text-gray-400 ring-1 ring-gray-500/50 shadow-[0_0_8px_rgba(107,114,128,0.3)]',
                  unselected: 'bg-gray-100/70 dark:bg-gray-800/50 text-gray-600 dark:text-gray-400 hover:bg-gray-200/70 dark:hover:bg-gray-700/50'
                };
            }
          };

          const colors = getStatusColors(status);
          
          return (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`
                px-3 py-1.5 rounded-full text-xs transition-all duration-200
                ${statusFilter === status ? colors.selected : colors.unselected}
              `}
            >
              {status === 'backlog' ? 'Backlog' : 
               status === 'in-progress' ? 'In Progress' : 
               status === 'review' ? 'Review' : 'Complete'}
            </button>
          );
        })}
      </div>

      <table className="w-full border-collapse table-fixed">
        <colgroup>
          <col className="w-16" /> {/* Order - fixed small width */}
          <col className="w-auto" />  {/* Task - takes remaining space */}
          <col className="w-24" />   {/* Status - compact */}
          <col className="w-28" />   {/* Feature - smaller width */}
          <col className="w-32" />   {/* Assignee - compact */}
          <col className="w-40" />   {/* Actions - fixed width for buttons */}
        </colgroup>
        <thead>
          <tr className="bg-white/80 dark:bg-black/80 backdrop-blur-sm sticky top-0 z-10">
            <th className="text-left p-3 font-mono border-b border-gray-300 dark:border-gray-800 relative">
              <div className="flex items-center gap-2">
                <span className={getHeaderColor('secondary')}>Order</span>
                <span className={`w-1 h-1 rounded-full ${getHeaderGlow('secondary')}`}></span>
              </div>
              {/* Header divider with glow matching board view */}
              <div className={`absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[1px] bg-purple-500/30 shadow-[0_0_10px_2px_rgba(168,85,247,0.2)]`}></div>
            </th>
            <th className="text-left p-3 font-mono border-b border-gray-300 dark:border-gray-800 relative">
              <div className="flex items-center gap-2">
                <span className={getHeaderColor('primary')}>Task</span>
                <span className={`w-1 h-1 rounded-full ${getHeaderGlow('primary')}`}></span>
              </div>
              <div className={`absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[1px] bg-cyan-500/30 shadow-[0_0_10px_2px_rgba(34,211,238,0.2)]`}></div>
            </th>
            <th className="text-left p-3 font-mono border-b border-gray-300 dark:border-gray-800 relative">
              <div className="flex items-center gap-2">
                <span className={getHeaderColor('secondary')}>Status</span>
                <span className={`w-1 h-1 rounded-full ${getHeaderGlow('secondary')}`}></span>
              </div>
              <div className={`absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[1px] bg-purple-500/30 shadow-[0_0_10px_2px_rgba(168,85,247,0.2)]`}></div>
            </th>
            <th className="text-left p-3 font-mono border-b border-gray-300 dark:border-gray-800 relative">
              <div className="flex items-center gap-2">
                <span className={getHeaderColor('secondary')}>Feature</span>
                <span className={`w-1 h-1 rounded-full ${getHeaderGlow('secondary')}`}></span>
              </div>
              <div className={`absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[1px] bg-purple-500/30 shadow-[0_0_10px_2px_rgba(168,85,247,0.2)]`}></div>
            </th>
            <th className="text-left p-3 font-mono border-b border-gray-300 dark:border-gray-800 relative">
              <div className="flex items-center gap-2">
                <span className={getHeaderColor('primary')}>Assignee</span>
                <span className={`w-1 h-1 rounded-full ${getHeaderGlow('primary')}`}></span>
              </div>
              <div className={`absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[1px] bg-cyan-500/30 shadow-[0_0_10px_2px_rgba(34,211,238,0.2)]`}></div>
            </th>
            <th className="text-center p-3 font-mono border-b border-gray-300 dark:border-gray-800 relative">
              <div className="flex items-center justify-center gap-2">
                <span className={getHeaderColor('primary')}>Actions</span>
                <span className={`w-1 h-1 rounded-full ${getHeaderGlow('primary')}`}></span>
              </div>
              <div className={`absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[1px] bg-cyan-500/30 shadow-[0_0_10px_2px_rgba(34,211,238,0.2)]`}></div>
            </th>
          </tr>
        </thead>
        <tbody>
          {statusFilter === 'all' ? (
            // Grouped by status when showing all
            statuses.map((status) => {
              const statusTasks = getTasksByStatus(status);
              return statusTasks.map((task, index) => (
                <DraggableTaskRow
                  key={task.id}
                  task={task}
                  index={index}  // This is the correct index within this status group
                  onTaskView={onTaskView}
                  onTaskComplete={onTaskComplete}
                  onTaskDelete={onTaskDelete}
                  onTaskReorder={onTaskReorder}
                  onTaskUpdate={onTaskUpdate}
                  tasksInStatus={statusTasks}  // Pass the tasks in this specific status
                />
              ));
            }).flat()  // Flatten the array since map returns arrays
          ) : (
            // Single status filter
            getTasksByStatus(statusFilter).map((task, index) => (
              <DraggableTaskRow
                key={task.id}
                task={task}
                index={index}
                onTaskView={onTaskView}
                onTaskComplete={onTaskComplete}
                onTaskDelete={onTaskDelete}
                onTaskReorder={onTaskReorder}
                onTaskUpdate={onTaskUpdate}
                tasksInStatus={getTasksByStatus(statusFilter)}
              />
            ))
          )}
          {/* Add Task Row */}
          <AddTaskRow onTaskCreate={onTaskCreate} tasks={tasks} statusFilter={statusFilter} />
        </tbody>
      </table>
    </div>
  );
}; 