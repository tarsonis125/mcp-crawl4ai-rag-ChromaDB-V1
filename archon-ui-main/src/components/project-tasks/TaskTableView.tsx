import React, { useState } from 'react';
import { useDrag, useDrop } from 'react-dnd';
import { Check, Trash2, Edit, Tag, User, Bot } from 'lucide-react';

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

interface DraggableTaskRowProps {
  task: Task;
  index: number;
  onTaskView: (task: Task) => void;
  onTaskComplete: (taskId: string) => void;
  onTaskDelete: (taskId: string) => void;
  onTaskReorder: (taskId: string, newOrder: number, status: Task['status']) => void;
  tasksInStatus: Task[];
}

const DraggableTaskRow = ({ 
  task, 
  index, 
  onTaskView, 
  onTaskComplete, 
  onTaskDelete, 
  onTaskReorder,
  tasksInStatus 
}: DraggableTaskRowProps) => {
  const [{ isDragging }, drag] = useDrag({
    type: ItemTypes.TASK,
    item: { id: task.id, index, status: task.status },
    collect: (monitor) => ({
      isDragging: !!monitor.isDragging(),
    }),
  });

  const [, drop] = useDrop({
    accept: ItemTypes.TASK,
    hover: (draggedItem: { id: string; index: number; status: Task['status'] }) => {
      if (draggedItem.id === task.id) return;
      if (draggedItem.status !== task.status) return;
      
      const draggedIndex = draggedItem.index;
      const hoveredIndex = index;
      
      if (draggedIndex === hoveredIndex) return;
      
      // Calculate new order based on position
      const newOrder = hoveredIndex + 1;
      onTaskReorder(draggedItem.id, newOrder, task.status);
      
      // Update the dragged item's index for continued hover calculations
      draggedItem.index = hoveredIndex;
    },
  });

  return (
    <tr 
      ref={(node) => drag(drop(node))}
      className={`
        group transition-all duration-300 cursor-move
        ${index % 2 === 0 ? 'bg-white/50 dark:bg-black/50' : 'bg-gray-50/80 dark:bg-gray-900/30'}
        hover:bg-gradient-to-r hover:from-cyan-50/70 hover:to-purple-50/70 dark:hover:from-cyan-900/20 dark:hover:to-purple-900/20
        border-b border-gray-200 dark:border-gray-800 last:border-b-0
        ${isDragging ? 'opacity-50' : ''}
      `}
    >
      <td className="p-3">
        <div className="flex items-center justify-center">
          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white ${getOrderColor(task.task_order)} ${getOrderGlow(task.task_order)}`}>
            {task.task_order}
          </div>
        </div>
      </td>
      <td className="p-3 text-gray-800 dark:text-gray-200 group-hover:text-gray-900 dark:group-hover:text-white transition-colors relative">
        <div className="absolute left-0 top-0 bottom-0 w-[3px] transition-all duration-300 group-hover:w-[4px] group-hover:opacity-100" 
             style={{
               backgroundColor: getOrderColor(task.task_order).replace('bg-', ''),
               boxShadow: `0 0 8px ${getOrderColor(task.task_order).includes('rose') ? '#f43f5e' : getOrderColor(task.task_order).includes('orange') ? '#f97316' : getOrderColor(task.task_order).includes('blue') ? '#3b82f6' : '#10b981'}`,
               opacity: 0.8
             }}
        />
        <div className="pl-2">{task.title}</div>
      </td>
      <td className="p-3">
        <div className="px-2 py-1 rounded text-xs inline-flex items-center gap-1" 
             style={{
               backgroundColor: task.status === 'backlog' ? 'rgba(107, 114, 128, 0.2)' : 
                               task.status === 'in-progress' ? 'rgba(59, 130, 246, 0.2)' : 
                               task.status === 'testing' ? 'rgba(168, 85, 247, 0.2)' : 'rgba(16, 185, 129, 0.2)',
               color: task.status === 'backlog' ? '#6b7280' : 
                     task.status === 'in-progress' ? '#3b82f6' : 
                     task.status === 'testing' ? '#a855f7' : '#10b981'
             }}
        >
          {task.status === 'backlog' ? 'Backlog' : 
           task.status === 'in-progress' ? 'In Progress' : 
           task.status === 'testing' ? 'Testing' : 'Complete'}
        </div>
      </td>
      <td className="p-3">
        <div className="flex items-center gap-2">
          <div className="flex items-center justify-center w-6 h-6 rounded-full bg-white/80 dark:bg-black/70 border border-gray-300 dark:border-gray-700 group-hover:border-cyan-500/50 transition-colors backdrop-blur-md" 
               style={{boxShadow: getAssigneeGlow(task.assignee?.name || 'User')}}
          >
            {getAssigneeIcon(task.assignee?.name || 'User')}
          </div>
          <span className="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">
            {task.assignee?.name || 'User'}
          </span>
        </div>
      </td>
      <td className="p-3">
        <div className="px-2 py-1 rounded text-xs inline-flex items-center gap-1" 
             style={{
               backgroundColor: `${task.featureColor}20`,
               color: task.featureColor
             }}
        >
          <Tag className="w-3 h-3" />
          {task.feature}
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
        </div>
      </td>
    </tr>
  );
};

export const TaskTableView = ({ 
  tasks, 
  onTaskView, 
  onTaskComplete, 
  onTaskDelete, 
  onTaskReorder 
}: TaskTableViewProps) => {
  const [statusFilter, setStatusFilter] = useState<Task['status'] | 'all'>('all');

  // Group tasks by status and sort by task_order
  const getTasksByStatus = (status: Task['status']) => {
    return tasks
      .filter(task => task.status === status)
      .sort((a, b) => a.task_order - b.task_order);
  };

  const filteredTasks = statusFilter === 'all' ? tasks : tasks.filter(task => task.status === statusFilter);
  const statuses: Task['status'][] = ['backlog', 'in-progress', 'testing', 'complete'];

  return (
    <div className="overflow-x-auto">
      {/* Status Filter */}
      <div className="mb-4 flex gap-2">
        <button
          onClick={() => setStatusFilter('all')}
          className={`px-3 py-1 rounded text-sm transition-colors ${
            statusFilter === 'all' 
              ? 'bg-cyan-500 text-white' 
              : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
          }`}
        >
          All Tasks
        </button>
        {statuses.map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={`px-3 py-1 rounded text-sm transition-colors ${
              statusFilter === status 
                ? 'bg-cyan-500 text-white' 
                : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
            }`}
          >
            {status === 'backlog' ? 'Backlog' : 
             status === 'in-progress' ? 'In Progress' : 
             status === 'testing' ? 'Testing' : 'Complete'}
          </button>
        ))}
      </div>

      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-gradient-to-r from-cyan-100/80 to-purple-100/80 dark:from-cyan-900/60 dark:to-purple-900/60 sticky top-0 z-10">
            <th className="text-left p-3 font-mono text-purple-600 dark:text-purple-400 border-b border-gray-300 dark:border-gray-800">
              <div className="flex items-center gap-2">
                Order
                <span className="w-1 h-1 rounded-full bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.6)]"></span>
              </div>
            </th>
            <th className="text-left p-3 font-mono text-cyan-600 dark:text-cyan-400 border-b border-gray-300 dark:border-gray-800">
              <div className="flex items-center gap-2">
                Task
                <span className="w-1 h-1 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(34,211,238,0.6)]"></span>
              </div>
            </th>
            <th className="text-left p-3 font-mono text-purple-600 dark:text-purple-400 border-b border-gray-300 dark:border-gray-800">
              <div className="flex items-center gap-2">
                Status
                <span className="w-1 h-1 rounded-full bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.6)]"></span>
              </div>
            </th>
            <th className="text-left p-3 font-mono text-cyan-600 dark:text-cyan-400 border-b border-gray-300 dark:border-gray-800">
              <div className="flex items-center gap-2">
                Assignee
                <span className="w-1 h-1 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(34,211,238,0.6)]"></span>
              </div>
            </th>
            <th className="text-left p-3 font-mono text-purple-600 dark:text-purple-400 border-b border-gray-300 dark:border-gray-800">
              <div className="flex items-center gap-2">
                Feature
                <span className="w-1 h-1 rounded-full bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.6)]"></span>
              </div>
            </th>
            <th className="text-center p-3 font-mono text-cyan-600 dark:text-cyan-400 border-b border-gray-300 dark:border-gray-800">
              <div className="flex items-center justify-center gap-2">
                Actions
                <span className="w-1 h-1 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(34,211,238,0.6)]"></span>
              </div>
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
                  index={index}
                  onTaskView={onTaskView}
                  onTaskComplete={onTaskComplete}
                  onTaskDelete={onTaskDelete}
                  onTaskReorder={onTaskReorder}
                  tasksInStatus={statusTasks}
                />
              ));
            })
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
                tasksInStatus={getTasksByStatus(statusFilter)}
              />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}; 