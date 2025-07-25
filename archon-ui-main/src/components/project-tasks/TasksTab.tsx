import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Table, LayoutGrid, Plus, Wifi, WifiOff, List } from 'lucide-react';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import { Toggle } from '../ui/Toggle';
import { projectService } from '../../services/projectService';
import { taskUpdateSocketIO } from '../../services/socketIOService';
import type { CreateTaskRequest, UpdateTaskRequest, DatabaseTaskStatus } from '../../types/project';
import { TaskTableView, Task } from './TaskTableView';
import { TaskBoardView } from './TaskBoardView';
import { EditTaskModal } from './EditTaskModal';

// Assignee utilities
const ASSIGNEE_OPTIONS = ['User', 'Archon', 'AI IDE Agent'] as const;

// Mapping functions for status conversion
const mapUIStatusToDBStatus = (uiStatus: Task['status']): DatabaseTaskStatus => {
  switch (uiStatus) {
    case 'backlog': return 'todo';
    case 'in-progress': return 'doing';
    case 'review': return 'review'; // Map UI 'review' to database 'review'
    case 'complete': return 'done';
    default: return 'todo';
  }
};

const mapDBStatusToUIStatus = (dbStatus: DatabaseTaskStatus): Task['status'] => {
  switch (dbStatus) {
    case 'todo': return 'backlog';
    case 'doing': return 'in-progress';
    case 'review': return 'review'; // Map database 'review' to UI 'review'
    case 'done': return 'complete';
    default: return 'backlog';
  }
};

// Helper function to map database task format to UI task format
const mapDatabaseTaskToUITask = (dbTask: any): Task => {
  return {
    id: dbTask.id,
    title: dbTask.title,
    description: dbTask.description || '',
    status: mapDBStatusToUIStatus(dbTask.status),
    assignee: {
      name: dbTask.assignee || 'User',
      avatar: ''
    },
    feature: dbTask.feature || 'General',
    featureColor: '#3b82f6', // Default blue color
    task_order: dbTask.task_order || 0,
  };
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
  const [viewMode, setViewMode] = useState<'table' | 'board'>('board');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [projectFeatures, setProjectFeatures] = useState<any[]>([]);
  const [isLoadingFeatures, setIsLoadingFeatures] = useState(false);
  const [isWebSocketConnected, setIsWebSocketConnected] = useState(false);
  
  const [isSavingTask, setIsSavingTask] = useState<boolean>(false);

  // Initialize tasks
  useEffect(() => {
    setTasks(initialTasks);
  }, [initialTasks]);

  // Load project features on component mount
  useEffect(() => {
    loadProjectFeatures();
  }, [projectId]);

  // WebSocket connection for real-time task updates
  useEffect(() => {
    if (!projectId) return;

    console.log('🔌 Setting up WebSocket connection for project:', projectId);
    
    // Check current connection state immediately
    if (taskUpdateSocketIO.isConnected()) {
      console.log('🔄 Already connected, setting state immediately');
      setIsWebSocketConnected(true);
    }
    
    // Debounce connection to avoid race conditions
    const connectionTimeout = setTimeout(() => {
      console.log('⏱️ Debounce period passed, establishing WebSocket connection...');
      
      const connectWebSocket = async () => {
        // Check if already connected to avoid double connections
        if (taskUpdateSocketIO.isConnected()) {
          console.log('🔄 WebSocket already connected, but rejoining project room');
          // Even if connected, we need to join the correct project room
          taskUpdateSocketIO.send({ type: 'join_project', project_id: projectId });
          setIsWebSocketConnected(true);
          return;
        }
        
        // Clear any existing handlers first
        taskUpdateSocketIO.disconnect();
        
        // Add connection state handler
        taskUpdateSocketIO.addStateChangeHandler((state) => {
          console.log(`🔌 WebSocket state changed: ${state}`);
          if (state === 'CONNECTED') {
            console.log('✅ Task updates WebSocket connected');
            setIsWebSocketConnected(true);
          } else if (state === 'DISCONNECTED' || state === 'FAILED') {
            setIsWebSocketConnected(false);
          }
        });
      
      // Add message handlers
      taskUpdateSocketIO.addMessageHandler('initial_tasks', (message) => {
        const initialWebSocketTasks = message.data || message;
        const uiTasks: Task[] = initialWebSocketTasks.map(mapDatabaseTaskToUITask);
        setTasks(uiTasks);
        onTasksChange(uiTasks);
      });
      
      taskUpdateSocketIO.addMessageHandler('task_created', (message) => {
        const newTask = message.data || message;
        console.log('🆕 Real-time task created:', newTask);
        const mappedTask = mapDatabaseTaskToUITask(newTask);
        setTasks(prev => {
          // Check if task already exists to prevent duplicates
          if (prev.some(task => task.id === newTask.id)) {
            console.log('Task already exists, skipping create');
            return prev;
          }
          const updated = [...prev, mappedTask];
          // Use setTimeout to avoid setState during render
          setTimeout(() => onTasksChange(updated), 0);
          return updated;
        });
      });
      
      taskUpdateSocketIO.addMessageHandler('task_updated', (message) => {
        const updatedTask = message.data || message;
          console.log('📝 Real-time task updated:', updatedTask, {
            isModalOpen,
            editingTaskId: editingTask?.id,
            timestamp: Date.now()
          });
          
          // Log if update happens while modal is open
          if (isModalOpen) {
            console.warn('[WebSocket] Task update received while modal is open!', {
              updatedTaskId: updatedTask.id,
              isEditingThisTask: editingTask?.id === updatedTask.id
            });
          }
          
          const mappedTask = mapDatabaseTaskToUITask(updatedTask);
          setTasks(prev => {
            // Check if this is actually a change
            const existingTask = prev.find(task => task.id === updatedTask.id);
            if (existingTask && JSON.stringify(existingTask) === JSON.stringify(mappedTask)) {
              console.log('No actual changes in task, skipping update');
              return prev;
          }
          
          const updated = prev.map(task => 
            task.id === updatedTask.id ? mappedTask : task
          );
          // Use setTimeout to avoid setState during render
          setTimeout(() => onTasksChange(updated), 0);
          return updated;
        });
      });

      // Handle bulk task updates from MCP DatabaseChangeDetector
      taskUpdateSocketIO.addMessageHandler('tasks_change', (message) => {
        const updatedTasks = message.data || message;
          setTasks(prev => {
            const updated = [...prev];
            
            // Update each changed task
            updatedTasks.forEach(updatedTask => {
              const mappedTask = mapDatabaseTaskToUITask(updatedTask);
              const index = updated.findIndex(task => task.id === updatedTask.id);
              if (index >= 0) {
                updated[index] = mappedTask;
              }
            });
            
          // Use setTimeout to avoid setState during render
          setTimeout(() => onTasksChange(updated), 0);
          return updated;
        });
      });
      
      taskUpdateSocketIO.addMessageHandler('task_deleted', (message) => {
        const deletedTask = message.data || message;
          console.log('🗑️ Real-time task deleted:', deletedTask);
          setTasks(prev => {
            const updated = prev.filter(task => task.id !== deletedTask.id);
            // Use setTimeout to avoid setState during render
          setTimeout(() => onTasksChange(updated), 0);
          return updated;
        });
      });
      
      taskUpdateSocketIO.addMessageHandler('task_archived', (message) => {
        const archivedTask = message.data || message;
          console.log('📦 Real-time task archived:', archivedTask);
          setTasks(prev => {
            const updated = prev.filter(task => task.id !== archivedTask.id);
            // Use setTimeout to avoid setState during render
          setTimeout(() => onTasksChange(updated), 0);
          return updated;
        });
      });
      
      // Add error handler
      taskUpdateSocketIO.addErrorHandler((error) => {
        console.error('❌ Task updates WebSocket error:', error);
        setIsWebSocketConnected(false);
      });
      
        // Connect to WebSocket
        try {
          await taskUpdateSocketIO.connect('/');
          
          // Join the project room after connection
          taskUpdateSocketIO.send({ type: 'join_project', project_id: projectId });
          
          // Add a small delay to ensure room join is processed
          await new Promise(resolve => setTimeout(resolve, 100));
          
          console.log('✅ Successfully joined project room:', projectId);
          
        } catch (error) {
          console.error('Failed to connect to task updates WebSocket:', error);
          setIsWebSocketConnected(false);
        }
      };

      connectWebSocket();
    }, 50); // 50ms debounce to let component settle (reduced for faster initial connection)

    // Cleanup on unmount or projectId change
    return () => {
      console.log('🧹 Cleaning up WebSocket connection');
      clearTimeout(connectionTimeout); // Clear the debounce timeout
      taskUpdateSocketIO.disconnect();
      setIsWebSocketConnected(false);
    };
  }, [projectId]); // Removed onTasksChange from dependency array

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


  // Modal management functions
  const openEditModal = async (task: Task) => {
    setEditingTask(task);
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingTask(null);
  };

  const saveTask = async (task: Task) => {
    setEditingTask(task);
    
    setIsSavingTask(true);
    try {
      let parentTaskId = task.id;
      
      if (task.id) {
        // Update existing task
        const updateData: UpdateTaskRequest = {
          title: task.title,
          description: task.description,
          status: mapUIStatusToDBStatus(task.status),
          assignee: task.assignee?.name || 'User',
          task_order: task.task_order,
          ...(task.feature && { feature: task.feature }),
          ...(task.featureColor && { featureColor: task.featureColor })
        };
        
        await projectService.updateTask(task.id, updateData);
      } else {
        // Create new task first to get UUID
        const createData: CreateTaskRequest = {
          project_id: projectId,
          title: task.title,
          description: task.description,
          status: mapUIStatusToDBStatus(task.status),
          assignee: task.assignee?.name || 'User',
          task_order: task.task_order,
          ...(task.feature && { feature: task.feature }),
          ...(task.featureColor && { featureColor: task.featureColor })
        };
        
        const createdTask = await projectService.createTask(createData);
        parentTaskId = createdTask.id;
      }
      
      // Reload tasks from backend
      const updatedTasks = await projectService.getTasksByProject(projectId);
      const uiTasks: Task[] = updatedTasks.map(mapDatabaseTaskToUITask);
      
      updateTasks(uiTasks);
      closeModal();
    } catch (error) {
      console.error('Failed to save task:', error);
      alert(`Failed to save task: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsSavingTask(false);
    }
  };

  // Update tasks helper
  const updateTasks = (newTasks: Task[]) => {
    setTasks(newTasks);
    onTasksChange(newTasks);
  };

  // Helper function to reorder tasks by status to ensure no gaps (1,2,3...)
  const reorderTasksByStatus = async (status: Task['status']) => {
    const tasksInStatus = tasks
      .filter(task => task.status === status)
      .sort((a, b) => a.task_order - b.task_order);
    
    const updatePromises = tasksInStatus.map((task, index) => 
      projectService.updateTask(task.id, { task_order: index + 1 })
    );
    
    await Promise.all(updatePromises);
  };

  // Helper function to get next available order number for a status
  const getNextOrderForStatus = (status: Task['status']): number => {
    const tasksInStatus = tasks.filter(task => 
      task.status === status
    );
    
    if (tasksInStatus.length === 0) return 1;
    
    const maxOrder = Math.max(...tasksInStatus.map(task => task.task_order));
    return maxOrder + 1;
  };

  // React DnD optimized task reordering - immediate visual feedback, async persistence  
  const handleTaskReorder = (taskId: string, targetIndex: number, status: Task['status']) => {
    console.log('REORDER: Moving task', taskId, 'to index', targetIndex, 'in status', status);
    
    // Get all tasks in the target status, sorted by current order
    const statusTasks = tasks
      .filter(task => task.status === status)
      .sort((a, b) => a.task_order - b.task_order);
    
    const otherTasks = tasks.filter(task => task.status !== status);
    
    // Find the moving task
    const movingTaskIndex = statusTasks.findIndex(task => task.id === taskId);
    if (movingTaskIndex === -1) {
      console.log('REORDER: Task not found in status');
      return;
    }
    
    // Prevent invalid moves
    if (targetIndex < 0 || targetIndex >= statusTasks.length) {
      console.log('REORDER: Invalid target index', targetIndex);
      return;
    }
    
    const movingTask = statusTasks[movingTaskIndex];
    console.log('REORDER: Moving', movingTask.title, 'from', movingTaskIndex, 'to', targetIndex);
    
    // Create new array with the task moved to the target position
    const reorderedTasks = [...statusTasks];
    
    // Remove the task from its current position
    reorderedTasks.splice(movingTaskIndex, 1);
    
    // Insert the task at the new position
    reorderedTasks.splice(targetIndex, 0, movingTask);
    
    // Renumber all tasks sequentially based on their new array positions
    const renumberedTasks = reorderedTasks.map((task, index) => ({
      ...task,
      task_order: index + 1
    }));
    
    // Update UI immediately for smooth visual feedback
    const allUpdatedTasks = [...otherTasks, ...renumberedTasks];
    updateTasks(allUpdatedTasks);
    
    // Persist to backend asynchronously (debounced)
    debouncedPersistReorder(renumberedTasks);
  };
  
  // Simple debounce function
  const debounce = (func: Function, delay: number) => {
    let timeoutId: NodeJS.Timeout;
    return (...args: any[]) => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => func(...args), delay);
    };
  };

  // Debounced persistence to avoid too many API calls during rapid dragging
  const debouncedPersistReorder = useCallback(
    debounce(async (tasksToUpdate: Task[]) => {
      try {
        console.log('REORDER: Persisting order changes for', tasksToUpdate.length, 'tasks');
        
        const updatePromises = tasksToUpdate.map(task => 
          projectService.updateTask(task.id, { task_order: task.task_order })
        );
        
        await Promise.all(updatePromises);
        console.log('REORDER: Persistence completed');
        
      } catch (error) {
        console.error('REORDER: Failed to persist order changes:', error);
        // Reload tasks from backend on error to restore correct state
        try {
          const updatedTasks = await projectService.getTasksByProject(projectId);
          const uiTasks: Task[] = updatedTasks.map(mapDatabaseTaskToUITask);
          updateTasks(uiTasks);
        } catch (reloadError) {
          console.error('REORDER: Failed to reload tasks:', reloadError);
        }
      }
    }, 500), // 500ms delay to batch rapid changes
    [projectId]
  );

  // Task move function (for board view)
  const moveTask = async (taskId: string, newStatus: Task['status']) => {
    console.log(`[TasksTab] Attempting to move task ${taskId} to new status: ${newStatus}`);
    try {
      const movingTask = tasks.find(task => task.id === taskId);
      if (!movingTask) {
        console.warn(`[TasksTab] Task ${taskId} not found for move operation.`);
        return;
      }
      
      const oldStatus = movingTask.status;
      const newOrder = getNextOrderForStatus(newStatus);

      console.log(`[TasksTab] Moving task ${movingTask.title} from ${oldStatus} to ${newStatus} with order ${newOrder}`);

      // Update the task with new status and order
      await projectService.updateTask(taskId, {
        status: mapUIStatusToDBStatus(newStatus),
        task_order: newOrder
      });
      console.log(`[TasksTab] Successfully updated task ${taskId} status in backend.`);
      
      // Update local state immediately
      const newTasks = tasks.map(task => task.id === taskId ? {
        ...task,
        status: newStatus,
        task_order: newOrder
      } : task);
      updateTasks(newTasks);
      console.log(`[TasksTab] UI state updated for task ${taskId}.`)
      
      // Reorder the old status to close gaps (if different from new status)
      if (oldStatus !== newStatus) {
        console.log(`[TasksTab] Reordering tasks in old status ${oldStatus}.`);
        await reorderTasksByStatus(oldStatus);
        
        // Reload tasks to reflect reordering
        console.log(`[TasksTab] Reloading all tasks after status change and reordering.`);
        const updatedTasks = await projectService.getTasksByProject(projectId);
        const uiTasks: Task[] = updatedTasks.map(mapDatabaseTaskToUITask);
        updateTasks(uiTasks);
        console.log(`[TasksTab] All tasks reloaded and UI updated.`);
      }
    } catch (error) {
      console.error(`[TasksTab] Failed to move task ${taskId}:`, error);
      alert(`Failed to move task: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  const completeTask = (taskId: string) => {
    console.log(`[TasksTab] Calling completeTask for ${taskId}`);
    moveTask(taskId, 'complete');
  };

  const deleteTask = async (task: Task) => {
    try {
      const deletingTask = tasks.find(t => t.id === task.id);
      if (!deletingTask) return;
      
      const taskStatus = deletingTask.status;
      
      // Delete the task
      await projectService.deleteTask(task.id);
      
      // Update local state immediately
      const newTasks = tasks.filter(t => t.id !== task.id);
      updateTasks(newTasks);
      
      // Reorder remaining tasks in the same status to close gaps
      await reorderTasksByStatus(taskStatus);
      
      // Reload tasks to reflect reordering
      const updatedTasks = await projectService.getTasksByProject(projectId);
      const uiTasks: Task[] = updatedTasks.map(mapDatabaseTaskToUITask);
      updateTasks(uiTasks);
    } catch (error) {
      console.error('Failed to delete task:', error);
      // Note: The toast notification for deletion is now handled by TaskBoardView and TaskTableView
    }
  };

  // Inline task creation function
  const createTaskInline = async (newTask: Omit<Task, 'id'>) => {
    try {
      // Auto-assign next order number if not provided
      const nextOrder = newTask.task_order || getNextOrderForStatus(newTask.status);
      
      const createData: CreateTaskRequest = {
        project_id: projectId,
        title: newTask.title,
        description: newTask.description,
        status: mapUIStatusToDBStatus(newTask.status),
        assignee: newTask.assignee?.name || 'User',
        task_order: nextOrder,
        ...(newTask.feature && { feature: newTask.feature }),
        ...(newTask.featureColor && { featureColor: newTask.featureColor })
      };
      
      await projectService.createTask(createData);
      
      // Reload tasks from backend to get the new task with ID
      const updatedTasks = await projectService.getTasksByProject(projectId);
      const uiTasks: Task[] = updatedTasks.map(mapDatabaseTaskToUITask);
      
      updateTasks(uiTasks);
    } catch (error) {
      console.error('Failed to create task:', error);
      throw error;
    }
  };

  // Inline task update function
  const updateTaskInline = async (taskId: string, updates: Partial<Task>) => {
    console.log(`[TasksTab] Inline update for task ${taskId} with updates:`, updates);
    try {
      const updateData: Partial<UpdateTaskRequest> = {};
      
      if (updates.title !== undefined) updateData.title = updates.title;
      if (updates.description !== undefined) updateData.description = updates.description;
      if (updates.status !== undefined) {
        console.log(`[TasksTab] Mapping UI status ${updates.status} to DB status.`);
        updateData.status = mapUIStatusToDBStatus(updates.status);
        console.log(`[TasksTab] Mapped status for ${taskId}: ${updates.status} -> ${updateData.status}`);
      }
      if (updates.assignee !== undefined) updateData.assignee = updates.assignee.name;
      if (updates.task_order !== undefined) updateData.task_order = updates.task_order;
      if (updates.feature !== undefined) updateData.feature = updates.feature;
      if (updates.featureColor !== undefined) updateData.featureColor = updates.featureColor;
      
      console.log(`[TasksTab] Sending update request for task ${taskId} to projectService:`, updateData);
      await projectService.updateTask(taskId, updateData);
      console.log(`[TasksTab] projectService.updateTask successful for ${taskId}.`);
      
      // Update local state optimistically
      const newTasks = tasks.map(task => 
        task.id === taskId ? { ...task, ...updates } : task
      );
      updateTasks(newTasks);
      console.log(`[TasksTab] UI state updated optimistically for task ${taskId}.`);
    } catch (error) {
      console.error(`[TasksTab] Failed to update task ${taskId} inline:`, error);
      alert(`Failed to update task: ${error instanceof Error ? error.message : 'Unknown error'}`);
      throw error;
    }
  };

  // Get tasks for priority selection with descriptive labels
  const getTasksForPrioritySelection = (status: Task['status']): Array<{value: number, label: string}> => {
    const tasksInStatus = tasks
      .filter(task => task.status === status && task.id !== editingTask?.id) // Exclude current task if editing
      .sort((a, b) => a.task_order - b.task_order);
    
    const options: Array<{value: number, label: string}> = [];
    
    if (tasksInStatus.length === 0) {
      // No tasks in this status
      options.push({ value: 1, label: "1 - First task in this status" });
    } else {
      // Add option to be first
      options.push({ 
        value: 1, 
        label: `1 - Before "${tasksInStatus[0].title.substring(0, 30)}${tasksInStatus[0].title.length > 30 ? '...' : ''}"` 
      });
      
      // Add options between existing tasks
      for (let i = 0; i < tasksInStatus.length - 1; i++) {
        const currentTask = tasksInStatus[i];
        const nextTask = tasksInStatus[i + 1];
        options.push({ 
          value: i + 2, 
          label: `${i + 2} - After "${currentTask.title.substring(0, 20)}${currentTask.title.length > 20 ? '...' : ''}", Before "${nextTask.title.substring(0, 20)}${nextTask.title.length > 20 ? '...' : ''}"` 
        });
      }
      
      // Add option to be last
      const lastTask = tasksInStatus[tasksInStatus.length - 1];
      options.push({ 
        value: tasksInStatus.length + 1, 
        label: `${tasksInStatus.length + 1} - After "${lastTask.title.substring(0, 30)}${lastTask.title.length > 30 ? '...' : ''}"` 
      });
    }
    
    return options;
  };

  // Memoized version of getTasksForPrioritySelection to prevent recalculation on every render
  const memoizedGetTasksForPrioritySelection = useMemo(
    () => getTasksForPrioritySelection,
    [tasks, editingTask?.id]
  );




  return (
    <DndProvider backend={HTML5Backend}>
      <div className="min-h-[70vh] relative">
        {/* Main content - Table or Board view */}
        <div className="relative h-[calc(100vh-220px)] overflow-auto">
          {viewMode === 'table' ? (
            <TaskTableView
              tasks={tasks}
              onTaskView={openEditModal}
              onTaskComplete={completeTask}
              onTaskDelete={deleteTask}
              onTaskReorder={handleTaskReorder}
              onTaskCreate={createTaskInline}
              onTaskUpdate={updateTaskInline}
            />
          ) : (
            <TaskBoardView
              tasks={tasks}
              onTaskView={openEditModal}
              onTaskComplete={completeTask}
              onTaskDelete={deleteTask}
              onTaskMove={moveTask}
              onTaskReorder={handleTaskReorder}
            />
          )}
        </div>

        {/* Fixed View Controls */}
        <div className="fixed bottom-6 left-0 right-0 flex justify-center z-50 pointer-events-none">
          <div className="flex items-center gap-4">
            {/* WebSocket Status Indicator */}
            <div className="flex items-center gap-2 px-3 py-2 bg-white/80 dark:bg-black/90 border border-gray-200 dark:border-gray-800 rounded-lg shadow-[0_0_20px_rgba(0,0,0,0.1)] dark:shadow-[0_0_20px_rgba(0,0,0,0.5)] backdrop-blur-md pointer-events-auto">
              {isWebSocketConnected ? (
                <>
                  <Wifi className="w-4 h-4 text-green-500" />
                  <span className="text-xs text-green-600 dark:text-green-400">Live</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-4 h-4 text-red-500" />
                  <span className="text-xs text-red-600 dark:text-red-400">Offline</span>
                </>
              )}
            </div>
            
            {/* Add Task Button with Luminous Style */}
            <button 
              onClick={() => {
                const defaultOrder = getTasksForPrioritySelection('backlog')[0]?.value || 1;
                setEditingTask({
                  id: '',
                  title: '',
                  description: '',
                  status: 'backlog',
                  assignee: { name: 'AI IDE Agent', avatar: '' },
                  feature: '',
                  featureColor: '#3b82f6',
                  task_order: defaultOrder
                });
                setIsModalOpen(true);
              }}
              className="relative px-5 py-2.5 flex items-center gap-2 bg-white/80 dark:bg-black/90 border border-gray-200 dark:border-gray-800 rounded-lg shadow-[0_0_20px_rgba(0,0,0,0.1)] dark:shadow-[0_0_20px_rgba(0,0,0,0.5)] backdrop-blur-md pointer-events-auto text-cyan-600 dark:text-cyan-400 hover:text-cyan-700 dark:hover:text-cyan-300 transition-all duration-300"
            >
              <Plus className="w-4 h-4 mr-1" />
              <span>Add Task</span>
              <span className="absolute bottom-0 left-[0%] right-[0%] w-[95%] mx-auto h-[2px] bg-cyan-500 shadow-[0_0_10px_2px_rgba(34,211,238,0.4)] dark:shadow-[0_0_20px_5px_rgba(34,211,238,0.7)]"></span>
            </button>
          
            {/* View Toggle Controls */}
            <div className="flex items-center bg-white/80 dark:bg-black/90 border border-gray-200 dark:border-gray-800 rounded-lg overflow-hidden shadow-[0_0_20px_rgba(0,0,0,0.1)] dark:shadow-[0_0_20px_rgba(0,0,0,0.5)] backdrop-blur-md pointer-events-auto">
              <button 
                onClick={() => setViewMode('table')} 
                className={`px-5 py-2.5 flex items-center gap-2 relative transition-all duration-300 ${viewMode === 'table' ? 'text-cyan-600 dark:text-cyan-400' : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-300'}`}
              >
                <Table className="w-4 h-4" />
                <span>Table</span>
                {viewMode === 'table' && <span className="absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[2px] bg-cyan-500 shadow-[0_0_10px_2px_rgba(34,211,238,0.4)] dark:shadow-[0_0_20px_5px_rgba(34,211,238,0.7)]"></span>}
              </button>
              <button 
                onClick={() => setViewMode('board')} 
                className={`px-5 py-2.5 flex items-center gap-2 relative transition-all duration-300 ${viewMode === 'board' ? 'text-purple-600 dark:text-purple-400' : 'text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-300'}`}
              >
                <LayoutGrid className="w-4 h-4" />
                <span>Board</span>
                {viewMode === 'board' && <span className="absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[2px] bg-purple-500 shadow-[0_0_10px_2px_rgba(168,85,247,0.4)] dark:shadow-[0_0_20px_5px_rgba(168,85,247,0.7)]"></span>}
              </button>
            </div>
          </div>
        </div>

        {/* Edit Task Modal */}
        <EditTaskModal
          isModalOpen={isModalOpen}
          editingTask={editingTask}
          projectFeatures={projectFeatures}
          isLoadingFeatures={isLoadingFeatures}
          isSavingTask={isSavingTask}
          onClose={closeModal}
          onSave={saveTask}
          getTasksForPrioritySelection={memoizedGetTasksForPrioritySelection}
        />
      </div>
    </DndProvider>
  );
};