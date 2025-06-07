import React, { useState, useRef, Component, useEffect } from 'react';
import { X, Edit, Check, Trash2, User, Tag, Table, LayoutGrid, ChevronDown, ChevronUp, AlertTriangle, ArrowRightCircle, RefreshCw, Plus, Bot } from 'lucide-react';
import { DndProvider, useDrag, useDrop } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import { Button } from '../ui/Button';
import { projectService } from '../../services/projectService';
import type { CreateTaskRequest, UpdateTaskRequest, DatabaseTaskStatus } from '../../types/project';
export interface Task {
  id: string;
  title: string;
  description: string;
  status: 'backlog' | 'in-progress' | 'testing' | 'complete';
  assignee: {
    name: 'User' | 'Archon' | 'AI IDE Agent';
    avatar: string;
  };
  feature: string;
  featureColor: string;
  priority?: 'low' | 'medium' | 'high' | 'critical';
}

// Assignee utilities
const ASSIGNEE_OPTIONS = ['User', 'Archon', 'AI IDE Agent'] as const;

// Mapping functions for status and priority conversion
const mapUIStatusToDBStatus = (uiStatus: Task['status']): DatabaseTaskStatus => {
  switch (uiStatus) {
    case 'backlog': return 'todo';
    case 'in-progress': return 'doing';
    case 'testing': return 'blocked'; 
    case 'complete': return 'done';
    default: return 'todo';
  }
};

const mapDBStatusToUIStatus = (dbStatus: DatabaseTaskStatus): Task['status'] => {
  switch (dbStatus) {
    case 'todo': return 'backlog';
    case 'doing': return 'in-progress';
    case 'blocked': return 'testing';
    case 'done': return 'complete';
    default: return 'backlog';
  }
};

const mapTaskOrderToPriority = (taskOrder: number): Task['priority'] => {
  if (taskOrder === 0) return 'critical';
  if (taskOrder === 1) return 'high';
  if (taskOrder === 2) return 'medium';
  return 'low';
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
// Item types for drag and drop
const ItemTypes = {
  TASK: 'task'
};
export const TasksTab = ({
  initialTasks,
  onTasksChange,
  projectId
}: {
  initialTasks: Task[];
  onTasksChange: (tasks: Task[]) => void;
  projectId: string;
}) => {
  // Change default view to 'board' instead of 'table'
  const [viewMode, setViewMode] = useState<'table' | 'board'>('board');
  const [tasks, setTasks] = useState(initialTasks);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [projectFeatures, setProjectFeatures] = useState<any[]>([]);
  const [isLoadingFeatures, setIsLoadingFeatures] = useState(false);

  // Load project features on component mount
  useEffect(() => {
    loadProjectFeatures();
  }, [projectId]);

  const loadProjectFeatures = async () => {
    if (!projectId) return;
    
    setIsLoadingFeatures(true);
    try {
      const response = await projectService.getProjectFeatures(projectId);
      setProjectFeatures(response.features || []);
    } catch (error) {
      console.error('Failed to load project features:', error);
      setProjectFeatures([]);
    } finally {
      setIsLoadingFeatures(false);
    }
  };

  // Add missing modal management functions
  const openEditModal = (task: Task) => {
    setEditingTask(task);
    setIsModalOpen(true);
  };
  const closeModal = () => {
    setIsModalOpen(false);
    setEditingTask(null);
  };
  const saveTask = async () => {
    if (!editingTask) return;
    
    console.log('💾 Starting saveTask...', { editingTask, projectId });
    
    try {
      if (editingTask.id) {
        // Update existing task
        const updateData: UpdateTaskRequest = {
          title: editingTask.title,
          description: editingTask.description,
          status: mapUIStatusToDBStatus(editingTask.status),
          assignee: editingTask.assignee?.name || 'User',
          // Convert priority to task_order (higher priority = lower number)
          task_order: editingTask.priority === 'critical' ? 0 
                    : editingTask.priority === 'high' ? 1 
                    : editingTask.priority === 'medium' ? 2 
                    : 3,
          ...(editingTask.feature && { feature: editingTask.feature }),
          ...(editingTask.featureColor && { featureColor: editingTask.featureColor })
        };
        
        console.log('🔄 Updating task...', updateData);
        const updatedTask = await projectService.updateTask(editingTask.id, updateData);
        console.log('✅ Task updated:', updatedTask);
      } else {
        // Create new task
        const createData: CreateTaskRequest = {
          project_id: projectId,
          title: editingTask.title,
          description: editingTask.description,
          status: mapUIStatusToDBStatus(editingTask.status),
          assignee: editingTask.assignee?.name || 'User',
          // Convert priority to task_order (higher priority = lower number)
          task_order: editingTask.priority === 'critical' ? 0 
                    : editingTask.priority === 'high' ? 1 
                    : editingTask.priority === 'medium' ? 2 
                    : 3,
          ...(editingTask.feature && { feature: editingTask.feature }),
          ...(editingTask.featureColor && { featureColor: editingTask.featureColor })
        };
        
        console.log('🆕 Creating task...', createData);
        const newTask = await projectService.createTask(createData);
        console.log('✅ Task created:', newTask);
      }
      
      // Reload tasks from backend to get updated data
      console.log('🔄 Reloading tasks from backend...');
      const updatedTasks = await projectService.getTasksByProject(projectId);
      console.log('📋 Raw tasks from backend:', updatedTasks);
      
      const uiTasks: Task[] = updatedTasks.map(task => ({
        id: task.id,
        title: task.title,
        description: task.description,
        status: mapDBStatusToUIStatus(task.status),
        assignee: {
          name: task.assignee || 'User',
          avatar: ''
        },
        feature: task.feature || 'General',
        featureColor: task.featureColor || '#6366f1',
        priority: mapTaskOrderToPriority(task.task_order || 0)
      }));
      
      console.log('🎨 Converted UI tasks:', uiTasks);
      updateTasks(uiTasks);
      closeModal();
      console.log('✅ saveTask completed successfully');
    } catch (error) {
      console.error('❌ Failed to save task:', error);
      // Show detailed error information
      if (error instanceof Error) {
        console.error('Error message:', error.message);
        console.error('Error stack:', error.stack);
      }
      alert(`Failed to save task: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };
  // Update setTasks to also call onTasksChange
  const updateTasks = (newTasks: Task[]) => {
    setTasks(newTasks);
    onTasksChange(newTasks);
  };
  // Update all task modification functions to use updateTasks
  const moveTask = async (taskId: string, newStatus: Task['status']) => {
    try {
      // Update task status in backend
      await projectService.updateTask(taskId, {
        status: mapUIStatusToDBStatus(newStatus)
      });
      
      // Update local state
      const newTasks = tasks.map(task => task.id === taskId ? {
        ...task,
        status: newStatus
      } : task);
      updateTasks(newTasks);
    } catch (error) {
      console.error('Failed to move task:', error);
      // TODO: Show error toast
    }
  };
  const completeTask = (taskId: string) => {
    moveTask(taskId, 'complete');
  };
  const deleteTask = async (taskId: string) => {
    try {
      // Delete task from backend
      await projectService.deleteTask(taskId);
      
      // Update local state
      const newTasks = tasks.filter(task => task.id !== taskId);
      updateTasks(newTasks);
    } catch (error) {
      console.error('Failed to delete task:', error);
      // TODO: Show error toast
    }
  };
  const getTasksByStatus = (status: Task['status']) => {
    return tasks.filter(task => task.status === status);
  };
  const getPriorityColor = (priority: Task['priority']) => {
    switch (priority) {
      case 'low':
        return 'bg-emerald-500';
      case 'medium':
        return 'bg-blue-500';
      case 'high':
        return 'bg-orange-500';
      case 'critical':
        return 'bg-rose-500';
      default:
        return 'bg-blue-500';
    }
  };
  const getPriorityGlow = (priority: Task['priority']) => {
    switch (priority) {
      case 'low':
        return 'shadow-[0_0_10px_rgba(16,185,129,0.7)]';
      case 'medium':
        return 'shadow-[0_0_10px_rgba(59,130,246,0.7)]';
      case 'high':
        return 'shadow-[0_0_10px_rgba(249,115,22,0.7)]';
      case 'critical':
        return 'shadow-[0_0_10px_rgba(244,63,94,0.7)]';
      default:
        return 'shadow-[0_0_10px_rgba(59,130,246,0.7)]';
    }
  };
  const getPriorityIcon = (priority: Task['priority']) => {
    switch (priority) {
      case 'low':
        return <ChevronDown className="w-3 h-3" />;
      case 'medium':
        return <ArrowRightCircle className="w-3 h-3" />;
      case 'high':
        return <ChevronUp className="w-3 h-3" />;
      case 'critical':
        return <AlertTriangle className="w-3 h-3" />;
      default:
        return <ArrowRightCircle className="w-3 h-3" />;
    }
  };
  return <DndProvider backend={HTML5Backend}>
      <div className="min-h-[70vh] relative">
        {/* Main content - Table or Board view */}
        <div className="relative h-[calc(100vh-220px)] overflow-auto">
          {viewMode === 'table' ? <TableView tasks={tasks} onTaskView={openEditModal} onTaskComplete={completeTask} onTaskDelete={deleteTask} onTaskMove={moveTask} getPriorityColor={getPriorityColor} getPriorityGlow={getPriorityGlow} getPriorityIcon={getPriorityIcon} /> : <div className="grid grid-cols-4 gap-0 h-full min-h-[70vh]">
              {/* Backlog Column */}
              <ColumnDropZone status="backlog" title="Backlog" tasks={getTasksByStatus('backlog')} onTaskMove={moveTask} onTaskView={openEditModal} onTaskComplete={completeTask} onTaskDelete={deleteTask} getPriorityColor={getPriorityColor} getPriorityGlow={getPriorityGlow} getPriorityIcon={getPriorityIcon} />
              {/* In Progress Column */}
              <ColumnDropZone status="in-progress" title="In Process" tasks={getTasksByStatus('in-progress')} onTaskMove={moveTask} onTaskView={openEditModal} onTaskComplete={completeTask} onTaskDelete={deleteTask} getPriorityColor={getPriorityColor} getPriorityGlow={getPriorityGlow} getPriorityIcon={getPriorityIcon} />
              {/* Testing Column */}
              <ColumnDropZone status="testing" title="Ready for Testing" tasks={getTasksByStatus('testing')} onTaskMove={moveTask} onTaskView={openEditModal} onTaskComplete={completeTask} onTaskDelete={deleteTask} getPriorityColor={getPriorityColor} getPriorityGlow={getPriorityGlow} getPriorityIcon={getPriorityIcon} />
              {/* Complete Column */}
              <ColumnDropZone status="complete" title="Complete" tasks={getTasksByStatus('complete')} onTaskMove={moveTask} onTaskView={openEditModal} onTaskComplete={completeTask} onTaskDelete={deleteTask} getPriorityColor={getPriorityColor} getPriorityGlow={getPriorityGlow} getPriorityIcon={getPriorityIcon} />
            </div>}
        </div>
        {/* Fixed View Controls - anchored to bottom of viewport */}
        <div className="fixed bottom-6 left-0 right-0 flex justify-center z-50 pointer-events-none">
          <div className="flex items-center gap-4">
            {/* New Task Button - updated to glass style with neon edge */}
            <button onClick={() => {
              setEditingTask({
                id: '',
                title: '',
                description: '',
                status: 'backlog',
                assignee: {
                  name: 'User',
                  avatar: ''
                },
                feature: '',
                featureColor: '#3b82f6',
                priority: 'medium'
              });
              setIsModalOpen(true);
            }} className="relative px-5 py-2.5 flex items-center gap-2 bg-white/80 dark:bg-black/90 border border-gray-200 dark:border-gray-800 rounded-lg shadow-[0_0_20px_rgba(0,0,0,0.1)] dark:shadow-[0_0_20px_rgba(0,0,0,0.5)] backdrop-blur-md pointer-events-auto text-cyan-600 dark:text-cyan-400 hover:text-cyan-700 dark:hover:text-cyan-300 transition-all duration-300">
              <Plus className="w-4 h-4 mr-1" />
              <span>New Task</span>
              {/* Neon bottom edge */}
              <span className="absolute bottom-0 left-[0%] right-[0%] w-[95%] mx-auto h-[2px] bg-cyan-500 shadow-[0_0_10px_2px_rgba(34,211,238,0.4)] dark:shadow-[0_0_20px_5px_rgba(34,211,238,0.7)]"></span>
            </button>
            {/* View Toggle */}
            <div className="flex items-center bg-white/80 dark:bg-black/90 border border-gray-200 dark:border-gray-800 rounded-lg overflow-hidden shadow-[0_0_20px_rgba(0,0,0,0.1)] dark:shadow-[0_0_20px_rgba(0,0,0,0.5)] backdrop-blur-md pointer-events-auto">
              <button onClick={() => setViewMode('table')} className={`
                  px-5 py-2.5 flex items-center gap-2 relative transition-all duration-300
                  ${viewMode === 'table' ? 'text-cyan-600 dark:text-cyan-400' : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-300'}
                `}>
                <Table className="w-4 h-4" />
                <span>Table</span>
                {viewMode === 'table' && <span className="absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[2px] bg-cyan-500 shadow-[0_0_10px_2px_rgba(34,211,238,0.4)] dark:shadow-[0_0_20px_5px_rgba(34,211,238,0.7)]"></span>}
              </button>
              <button onClick={() => setViewMode('board')} className={`
                  px-5 py-2.5 flex items-center gap-2 relative transition-all duration-300
                  ${viewMode === 'board' ? 'text-purple-600 dark:text-purple-400' : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-300'}
                `}>
                <LayoutGrid className="w-4 h-4" />
                <span>Board</span>
                {viewMode === 'board' && <span className="absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[2px] bg-purple-500 shadow-[0_0_10px_2px_rgba(168,85,247,0.4)] dark:shadow-[0_0_20px_5px_rgba(168,85,247,0.7)]"></span>}
              </button>
            </div>
          </div>
        </div>
        {/* Edit Task Modal */}
        {isModalOpen && <div className="fixed inset-0 bg-gray-500/50 dark:bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
            <div className="relative p-6 rounded-md backdrop-blur-md w-full max-w-2xl
                bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30
                border border-gray-200 dark:border-zinc-800/50
                shadow-[0_10px_30px_-15px_rgba(0,0,0,0.1)] dark:shadow-[0_10px_30px_-15px_rgba(0,0,0,0.7)]
                before:content-[''] before:absolute before:top-0 before:left-0 before:right-0 before:h-[2px] 
                before:rounded-t-[4px] before:bg-gradient-to-r before:from-cyan-500 before:to-fuchsia-500 
                before:shadow-[0_0_10px_2px_rgba(34,211,238,0.4)] dark:before:shadow-[0_0_20px_5px_rgba(34,211,238,0.7)]
                after:content-[''] after:absolute after:top-0 after:left-0 after:right-0 after:h-16
                after:bg-gradient-to-b after:from-cyan-100 after:to-white dark:after:from-cyan-500/20 dark:after:to-fuchsia-500/5
                after:rounded-t-md after:pointer-events-none">
              <div className="relative z-10">
                <div className="flex justify-between items-center mb-6">
                  <h3 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-fuchsia-500 text-transparent bg-clip-text">
                    {editingTask ? 'Edit Task' : 'New Task'}
                  </h3>
                  <button onClick={closeModal} className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-white transition-colors">
                    <X className="w-5 h-5" />
                  </button>
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="block text-gray-700 dark:text-gray-300 mb-1">
                      Title
                    </label>
                    <input type="text" value={editingTask?.title || ''} onChange={e => setEditingTask(editingTask ? {
                  ...editingTask,
                  title: e.target.value
                } : null)} className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white rounded-md py-2 px-3 focus:outline-none focus:border-cyan-400 focus:shadow-[0_0_10px_rgba(34,211,238,0.2)] transition-all duration-300" />
                  </div>
                  <div>
                    <label className="block text-gray-700 dark:text-gray-300 mb-1">
                      Description
                    </label>
                    <textarea value={editingTask?.description || ''} onChange={e => setEditingTask(editingTask ? {
                  ...editingTask,
                  description: e.target.value
                } : null)} rows={5} className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-white rounded-md py-2 px-3 focus:outline-none focus:border-cyan-400 focus:shadow-[0_0_10px_rgba(34,211,238,0.2)] transition-all duration-300" />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-gray-700 dark:text-gray-300 mb-1">
                        Status
                      </label>
                      <select value={editingTask?.status || 'backlog'} onChange={e => setEditingTask(editingTask ? {
                    ...editingTask,
                    status: e.target.value as Task['status']
                  } : null)} className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-white rounded-md py-2 px-3 focus:outline-none focus:border-cyan-400 focus:shadow-[0_0_10px_rgba(34,211,238,0.2)] transition-all duration-300">
                        <option value="backlog">Backlog</option>
                        <option value="in-progress">In Process</option>
                        <option value="testing">Ready for Testing</option>
                        <option value="complete">Complete</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-gray-700 dark:text-gray-300 mb-1">
                        Feature
                      </label>
                      <div className="relative">
                        <input 
                          type="text" 
                          value={editingTask?.feature || ''} 
                          onChange={e => setEditingTask(editingTask ? {
                            ...editingTask,
                            feature: e.target.value
                          } : null)} 
                          placeholder="Type feature name or select from list"
                          className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-white rounded-md py-2 px-3 pr-10 focus:outline-none focus:border-cyan-400 focus:shadow-[0_0_10px_rgba(34,211,238,0.2)] transition-all duration-300" 
                          list="features-list"
                        />
                        <datalist id="features-list">
                          {projectFeatures.map((feature) => (
                            <option key={feature.id} value={feature.label}>
                              {feature.label} ({feature.type})
                            </option>
                          ))}
                        </datalist>
                        {isLoadingFeatures && (
                          <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                            <RefreshCw className="w-4 h-4 animate-spin text-cyan-400" />
                          </div>
                        )}
                      </div>
                      {projectFeatures.length > 0 && (
                        <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                          Available features: {projectFeatures.map(f => f.label).join(', ')}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-gray-700 dark:text-gray-300 mb-1">
                        Assignee
                      </label>
                      <select 
                        value={editingTask?.assignee?.name || 'User'} 
                        onChange={e => setEditingTask(editingTask ? {
                          ...editingTask,
                          assignee: {
                            name: e.target.value as 'User' | 'Archon' | 'AI IDE Agent',
                            avatar: ''
                          }
                        } : null)} 
                        className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-white rounded-md py-2 px-3 focus:outline-none focus:border-cyan-400 focus:shadow-[0_0_10px_rgba(34,211,238,0.2)] transition-all duration-300"
                      >
                        {ASSIGNEE_OPTIONS.map(option => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-gray-700 dark:text-gray-300 mb-1">
                        Priority
                      </label>
                      <select value={editingTask?.priority || 'medium'} onChange={e => setEditingTask(editingTask ? {
                    ...editingTask,
                    priority: e.target.value as Task['priority']
                  } : null)} className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-700 dark:text-white rounded-md py-2 px-3 focus:outline-none focus:border-cyan-400 focus:shadow-[0_0_10px_rgba(34,211,238,0.2)] transition-all duration-300">
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                        <option value="critical">Critical</option>
                      </select>
                    </div>
                  </div>
                </div>
                <div className="flex justify-end gap-3 mt-6">
                  <Button onClick={closeModal} variant="ghost">
                    Cancel
                  </Button>
                  <Button onClick={saveTask} variant="primary" accentColor="cyan" className="shadow-lg shadow-cyan-500/20">
                    {editingTask ? 'Save Changes' : 'Create Task'}
                  </Button>
                </div>
              </div>
            </div>
          </div>}
      </div>
    </DndProvider>;
};
// Table View Component
interface TableViewProps {
  tasks: Task[];
  onTaskView: (task: Task) => void;
  onTaskComplete: (taskId: string) => void;
  onTaskDelete: (taskId: string) => void;
  onTaskMove: (taskId: string, newStatus: Task['status']) => void;
  getPriorityColor: (priority: Task['priority']) => string;
  getPriorityGlow: (priority: Task['priority']) => string;
  getPriorityIcon: (priority: Task['priority']) => React.ReactNode;
}
const TableView = ({
  tasks,
  onTaskView,
  onTaskComplete,
  onTaskDelete,
  onTaskMove,
  getPriorityColor,
  getPriorityGlow,
  getPriorityIcon
}: TableViewProps) => {
  const [draggedTaskId, setDraggedTaskId] = useState<string | null>(null);
  // Sort tasks by priority
  const sortedTasks = [...tasks].sort((a, b) => {
    const priorityOrder = {
      critical: 0,
      high: 1,
      medium: 2,
      low: 3
    };
    return priorityOrder[a.priority || 'medium'] - priorityOrder[b.priority || 'medium'];
  });
  return <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-gradient-to-r from-cyan-100/80 to-purple-100/80 dark:from-cyan-900/60 dark:to-purple-900/60 sticky top-0 z-10">
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
                Priority
                <span className="w-1 h-1 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(34,211,238,0.6)]"></span>
              </div>
            </th>
            <th className="text-left p-3 font-mono text-purple-600 dark:text-purple-400 border-b border-gray-300 dark:border-gray-800">
              <div className="flex items-center gap-2">
                Assignee
                <span className="w-1 h-1 rounded-full bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.6)]"></span>
              </div>
            </th>
            <th className="text-left p-3 font-mono text-cyan-600 dark:text-cyan-400 border-b border-gray-300 dark:border-gray-800">
              <div className="flex items-center gap-2">
                Feature
                <span className="w-1 h-1 rounded-full bg-cyan-500 shadow-[0_0_8px_rgba(34,211,238,0.6)]"></span>
              </div>
            </th>
            <th className="text-center p-3 font-mono text-purple-600 dark:text-purple-400 border-b border-gray-300 dark:border-gray-800">
              <div className="flex items-center justify-center gap-2">
                Actions
                <span className="w-1 h-1 rounded-full bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.6)]"></span>
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedTasks.map((task, index) => <tr key={task.id} className={`
                group transition-all duration-300 cursor-pointer
                ${index % 2 === 0 ? 'bg-white/50 dark:bg-black/50' : 'bg-gray-50/80 dark:bg-gray-900/30'}
                hover:bg-gradient-to-r hover:from-cyan-50/70 hover:to-purple-50/70 dark:hover:from-cyan-900/20 dark:hover:to-purple-900/20
                border-b border-gray-200 dark:border-gray-800 last:border-b-0
              `} draggable onDragStart={() => setDraggedTaskId(task.id)} onDragEnd={() => setDraggedTaskId(null)}>
              <td className="p-3 text-gray-800 dark:text-gray-200 group-hover:text-gray-900 dark:group-hover:text-white transition-colors relative">
                {/* Priority indicator */}
                <div className="absolute left-0 top-0 bottom-0 w-[3px] transition-all duration-300 group-hover:w-[4px] group-hover:opacity-100" style={{
              backgroundColor: task.priority ? getPriorityColor(task.priority).replace('bg-', '') : '#3b82f6',
              boxShadow: `0 0 8px ${task.priority === 'critical' ? '#f43f5e' : task.priority === 'high' ? '#f97316' : task.priority === 'low' ? '#10b981' : '#3b82f6'}`,
              opacity: 0.8
            }}></div>
                <div className="pl-2">{task.title}</div>
              </td>
              <td className="p-3">
                <div className="px-2 py-1 rounded text-xs inline-flex items-center gap-1" style={{
              backgroundColor: task.status === 'backlog' ? 'rgba(107, 114, 128, 0.2)' : task.status === 'in-progress' ? 'rgba(59, 130, 246, 0.2)' : task.status === 'testing' ? 'rgba(168, 85, 247, 0.2)' : 'rgba(16, 185, 129, 0.2)',
              color: task.status === 'backlog' ? '#6b7280' : task.status === 'in-progress' ? '#3b82f6' : task.status === 'testing' ? '#a855f7' : '#10b981'
            }}>
                  {task.status === 'backlog' ? 'Backlog' : task.status === 'in-progress' ? 'In Progress' : task.status === 'testing' ? 'Testing' : 'Complete'}
                </div>
              </td>
              <td className="p-3">
                <div className="flex items-center gap-1.5">
                  <div className={`w-4 h-4 rounded-full flex items-center justify-center ${getPriorityColor(task.priority || 'medium')} ${getPriorityGlow(task.priority || 'medium')}`}>
                    {getPriorityIcon(task.priority || 'medium')}
                  </div>
                  <span className="text-xs capitalize text-gray-700 dark:text-gray-300">
                    {task.priority || 'Medium'}
                  </span>
                </div>
              </td>
              <td className="p-3">
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-6 h-6 rounded-full bg-white/80 dark:bg-black/70 border border-gray-300 dark:border-gray-700 group-hover:border-cyan-500/50 transition-colors backdrop-blur-md" style={{boxShadow: getAssigneeGlow(task.assignee?.name || 'User')}}>
                    {getAssigneeIcon(task.assignee?.name || 'User')}
                  </div>
                  <span className="text-sm text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">
                    {task.assignee?.name || 'User'}
                  </span>
                </div>
              </td>
              <td className="p-3">
                <div className="px-2 py-1 rounded text-xs inline-flex items-center gap-1" style={{
              backgroundColor: `${task.featureColor}20`,
              color: task.featureColor
            }}>
                  <Tag className="w-3 h-3" />
                  {task.feature}
                </div>
              </td>
              <td className="p-3">
                <div className="flex justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => onTaskDelete(task.id)} className="p-1.5 rounded-full bg-red-500/20 text-red-500 hover:bg-red-500/30 hover:shadow-[0_0_10px_rgba(239,68,68,0.3)] transition-all duration-300">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => onTaskComplete(task.id)} className="p-1.5 rounded-full bg-green-500/20 text-green-500 hover:bg-green-500/30 hover:shadow-[0_0_10px_rgba(34,197,94,0.3)] transition-all duration-300">
                    <Check className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => onTaskView(task)} className="p-1.5 rounded-full bg-cyan-500/20 text-cyan-500 hover:bg-cyan-500/30 hover:shadow-[0_0_10px_rgba(34,211,238,0.3)] transition-all duration-300">
                    <Edit className="w-3.5 h-3.5" />
                  </button>
                </div>
              </td>
            </tr>)}
        </tbody>
      </table>
    </div>;
};
interface ColumnDropZoneProps {
  status: Task['status'];
  title: string;
  tasks: Task[];
  onTaskMove: (taskId: string, newStatus: Task['status']) => void;
  onTaskView: (task: Task) => void;
  onTaskComplete: (taskId: string) => void;
  onTaskDelete: (taskId: string) => void;
  getPriorityColor: (priority: Task['priority']) => string;
  getPriorityGlow: (priority: Task['priority']) => string;
  getPriorityIcon: (priority: Task['priority']) => React.ReactNode;
}
const ColumnDropZone = ({
  status,
  title,
  tasks,
  onTaskMove,
  onTaskView,
  onTaskComplete,
  onTaskDelete,
  getPriorityColor,
  getPriorityGlow,
  getPriorityIcon
}: ColumnDropZoneProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const [{
    isOver
  }, drop] = useDrop({
    accept: ItemTypes.TASK,
    drop: (item: {
      id: string;
      status: string;
    }) => {
      if (item.status !== status) {
        onTaskMove(item.id, status);
      }
    },
    collect: monitor => ({
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
      case 'testing':
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
      case 'testing':
        return 'bg-purple-500/30 shadow-[0_0_10px_2px_rgba(168,85,247,0.2)]';
      case 'complete':
        return 'bg-green-500/30 shadow-[0_0_10px_2px_rgba(16,185,129,0.2)]';
    }
  };
  return <div ref={ref} className={`flex flex-col bg-white/20 dark:bg-black/30 ${isOver ? 'bg-gray-100/50 dark:bg-gray-800/20 border-t-2 border-t-[#00ff00] shadow-[inset_0_1px_10px_rgba(0,255,0,0.1)]' : ''} transition-colors duration-200 h-full`}>
      <div className="text-center py-3 relative sticky top-0 z-10 bg-white/80 dark:bg-black/80 backdrop-blur-sm">
        <h3 className={`font-mono ${getColumnColor()} text-sm`}>{title}</h3>
        {/* Column header divider with glow */}
        <div className={`absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[1px] ${getColumnGlow()}`}></div>
      </div>
      <div className="px-1 flex-1 overflow-y-auto space-y-3 py-3">
        {tasks.map(task => <DraggableTaskCard key={task.id} task={task} onView={() => onTaskView(task)} onComplete={() => onTaskComplete(task.id)} onDelete={() => onTaskDelete(task.id)} getPriorityColor={getPriorityColor} getPriorityGlow={getPriorityGlow} getPriorityIcon={getPriorityIcon} />)}
      </div>
    </div>;
};
interface DraggableTaskCardProps {
  task: Task;
  onView: () => void;
  onComplete: () => void;
  onDelete: () => void;
  getPriorityColor: (priority: Task['priority']) => string;
  getPriorityGlow: (priority: Task['priority']) => string;
  getPriorityIcon: (priority: Task['priority']) => React.ReactNode;
}
const DraggableTaskCard = ({
  task,
  onView,
  onComplete,
  onDelete,
  getPriorityColor,
  getPriorityGlow,
  getPriorityIcon
}: DraggableTaskCardProps) => {
  const [{
    isDragging
  }, drag] = useDrag({
    type: ItemTypes.TASK,
    item: {
      id: task.id,
      status: task.status
    },
    collect: monitor => ({
      isDragging: !!monitor.isDragging()
    })
  });
  const [isFlipped, setIsFlipped] = useState(false);
  const toggleFlip = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsFlipped(!isFlipped);
  };
  return <div ref={drag} className={`flip-card h-[140px] w-full cursor-move ${isDragging ? 'opacity-50 scale-95' : 'opacity-100'} transition-all duration-300`} style={{
    perspective: '1000px'
  }}>
      <div className={`relative w-full h-full transition-transform duration-500 transform-style-preserve-3d ${isFlipped ? 'rotate-y-180' : ''}`}>
        {/* Front side */}
        <div className="absolute w-full h-full backface-hidden bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border border-gray-200 dark:border-gray-800 rounded-lg p-3 hover:border-gray-300 dark:hover:border-gray-700 transition-all duration-300 group shadow-[0_10px_30px_-15px_rgba(0,0,0,0.1)] dark:shadow-[0_10px_30px_-15px_rgba(0,0,0,0.7)]">
          {/* Priority indicator */}
          <div className={`absolute left-0 top-0 bottom-0 w-[3px] ${getPriorityColor(task.priority || 'medium')} ${getPriorityGlow(task.priority || 'medium')} rounded-l-lg opacity-80 group-hover:w-[4px] group-hover:opacity-100 transition-all duration-300`}></div>
          <div className="flex items-center gap-2 mb-2 pl-1.5">
            <div className="px-2 py-1 rounded-md text-xs font-medium flex items-center gap-1 backdrop-blur-md" style={{
            backgroundColor: `${task.featureColor}20`,
            color: task.featureColor,
            boxShadow: `0 0 10px ${task.featureColor}20`
          }}>
              <Tag className="w-3 h-3" />
              {task.feature}
            </div>
            {/* Action buttons group */}
            <div className="ml-auto flex items-center gap-1.5">
              <button onClick={e => {
              e.stopPropagation();
              onDelete();
            }} className="w-5 h-5 rounded-full flex items-center justify-center bg-red-100/80 dark:bg-red-500/20 text-red-600 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-500/30 hover:shadow-[0_0_10px_rgba(239,68,68,0.3)] transition-all duration-300">
                <Trash2 className="w-3 h-3" />
              </button>
              <button onClick={e => {
              e.stopPropagation();
              onView();
            }} className="w-5 h-5 rounded-full flex items-center justify-center bg-cyan-100/80 dark:bg-cyan-500/20 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-200 dark:hover:bg-cyan-500/30 hover:shadow-[0_0_10px_rgba(34,211,238,0.3)] transition-all duration-300">
                <Edit className="w-3 h-3" />
              </button>
              <button onClick={toggleFlip} className="w-5 h-5 rounded-full flex items-center justify-center bg-cyan-100/80 dark:bg-cyan-500/20 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-200 dark:hover:bg-cyan-500/30 hover:shadow-[0_0_10px_rgba(34,211,238,0.3)] transition-all duration-300">
                <RefreshCw className="w-3 h-3" />
              </button>
            </div>
          </div>
          <h4 className="font-medium text-gray-900 dark:text-white mb-2 pl-1.5">
            {task.title}
          </h4>
          <div className="flex items-center text-gray-500 text-xs absolute bottom-3 left-3 pl-1.5">
            <div className="flex items-center gap-2">
              <div className="flex items-center justify-center w-5 h-5 rounded-full bg-white/80 dark:bg-black/70 border border-gray-300/50 dark:border-gray-700/50 backdrop-blur-md" style={{boxShadow: getAssigneeGlow(task.assignee?.name || 'User')}}>
                {getAssigneeIcon(task.assignee?.name || 'User')}
              </div>
              <span className="text-gray-600 dark:text-gray-400">{task.assignee?.name || 'User'}</span>
            </div>
          </div>
        </div>
        {/* Back side */}
        <div className="absolute w-full h-full backface-hidden bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border border-gray-200 dark:border-gray-800 rounded-lg p-3 rotate-y-180 transition-all duration-300 group shadow-[0_10px_30px_-15px_rgba(0,0,0,0.1)] dark:shadow-[0_10px_30px_-15px_rgba(0,0,0,0.7)]">
          {/* Priority indicator */}
          <div className={`absolute left-0 top-0 bottom-0 w-[3px] ${getPriorityColor(task.priority || 'medium')} ${getPriorityGlow(task.priority || 'medium')} rounded-l-lg opacity-80 group-hover:w-[4px] group-hover:opacity-100 transition-all duration-300`}></div>
          <div className="flex items-center gap-2 mb-2 pl-1.5">
            <h4 className="font-medium text-gray-900 dark:text-white">
              {task.title}
            </h4>
            <button onClick={toggleFlip} className="ml-auto w-5 h-5 rounded-full flex items-center justify-center bg-cyan-100/80 dark:bg-cyan-500/20 text-cyan-600 dark:text-cyan-400 hover:bg-cyan-200 dark:hover:bg-cyan-500/30 hover:shadow-[0_0_10px_rgba(34,211,238,0.3)] transition-all duration-300">
              <RefreshCw className="w-3 h-3" />
            </button>
          </div>
          <div className="h-[75px] overflow-y-auto text-gray-700 dark:text-gray-300 text-xs mb-2 scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-700 scrollbar-track-transparent pr-1 pl-1.5">
            <p>{task.description}</p>
          </div>
        </div>
      </div>
    </div>;
};