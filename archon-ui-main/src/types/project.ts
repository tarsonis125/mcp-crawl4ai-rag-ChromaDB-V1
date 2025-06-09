// TypeScript types for Project Management system
// Based on database schema in migration/archon_tasks.sql

// Database status enum mapping
export type DatabaseTaskStatus = 'todo' | 'doing' | 'review' | 'done';

// UI status enum (used in current TasksTab)
export type UITaskStatus = 'backlog' | 'in-progress' | 'review' | 'complete';

// Priority levels
export type TaskPriority = 'low' | 'medium' | 'high' | 'critical';

// Project color themes (from existing UI)
export type ProjectColor = 'cyan' | 'purple' | 'pink' | 'blue' | 'orange' | 'green';

// Assignee type - simplified to predefined options
export type Assignee = 'User' | 'Archon' | 'AI IDE Agent';

// Base Project interface (matches database schema)
export interface Project {
  id: string;
  title: string;
  prd?: Record<string, any>; // JSONB field
  docs?: any[]; // JSONB field
  features?: any[]; // JSONB field  
  data?: any[]; // JSONB field
  github_repo?: string;
  created_at: string;
  updated_at: string;
  technical_sources?: string[]; // Array of source IDs from project_sources table
  business_sources?: string[]; // Array of source IDs from project_sources table
  
  // Extended UI properties (stored in JSONB fields)
  description?: string;
  icon?: string;
  color?: ProjectColor;
  progress?: number;
  updated?: string; // Human-readable format
}

// Base Task interface (matches database schema)
export interface Task {
  id: string;
  project_id: string;
  parent_task_id?: string;
  title: string;
  description: string;
  status: DatabaseTaskStatus;
  assignee: Assignee; // Now a database column with enum constraint
  task_order: number; // New database column for priority ordering
  feature?: string; // New database column for feature name
  sources?: any[]; // JSONB field
  code_examples?: any[]; // JSONB field
  created_at: string;
  updated_at: string;
  
  // Soft delete fields
  archived?: boolean; // Soft delete flag
  archived_at?: string; // Timestamp when archived
  archived_by?: string; // User/system that archived the task
  
  // Extended UI properties (can be stored in sources JSONB)
  featureColor?: string;
  priority?: TaskPriority;
  
  // UI-specific computed properties
  uiStatus?: UITaskStatus; // Computed from database status
}

// Create project request
export interface CreateProjectRequest {
  title: string;
  description?: string;
  icon?: string;
  color?: ProjectColor;
  github_repo?: string;
  prd?: Record<string, any>;
  docs?: any[];
  features?: any[];
  data?: any[];
  technical_sources?: string[];
  business_sources?: string[];
}

// Update project request
export interface UpdateProjectRequest {
  title?: string;
  description?: string;
  icon?: string;
  color?: ProjectColor;
  github_repo?: string;
  prd?: Record<string, any>;
  docs?: any[];
  features?: any[];
  data?: any[];
  technical_sources?: string[];
  business_sources?: string[];
}

// Create task request
export interface CreateTaskRequest {
  project_id: string;
  parent_task_id?: string;
  title: string;
  description: string;
  status?: DatabaseTaskStatus;
  assignee?: Assignee;
  task_order?: number;
  feature?: string;
  featureColor?: string;
  priority?: TaskPriority;
  sources?: any[];
  code_examples?: any[];
}

// Update task request
export interface UpdateTaskRequest {
  title?: string;
  description?: string;
  status?: DatabaseTaskStatus;
  assignee?: Assignee;
  task_order?: number;
  feature?: string;
  featureColor?: string;
  priority?: TaskPriority;
  sources?: any[];
  code_examples?: any[];
}

// MCP tool response types
export interface MCPToolResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

// WebSocket event types for real-time updates
export interface ProjectUpdateEvent {
  type: 'PROJECT_UPDATED' | 'PROJECT_CREATED' | 'PROJECT_DELETED';
  projectId: string;
  userId: string;
  timestamp: string;
  data: Partial<Project>;
}

export interface TaskUpdateEvent {
  type: 'TASK_MOVED' | 'TASK_CREATED' | 'TASK_UPDATED' | 'TASK_DELETED' | 'TASK_ARCHIVED';
  taskId: string;
  projectId: string;
  userId: string;
  timestamp: string;
  data: Partial<Task>;
}

export type ProjectManagementEvent = ProjectUpdateEvent | TaskUpdateEvent;

// Utility type for paginated responses
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  hasMore: boolean;
}

// Status mapping utilities
export const statusMappings = {
  // Database to UI status mapping
  dbToUI: {
    'todo': 'backlog',
    'doing': 'in-progress', 
    'review': 'review', // Map database 'review' to UI 'review'
    'done': 'complete'
  } as const,
  
  // UI to Database status mapping
  uiToDB: {
    'backlog': 'todo',
    'in-progress': 'doing',
    'review': 'review', // Map UI 'review' to database 'review'
    'complete': 'done'
  } as const
} as const;

// Helper function to convert database task to UI task
export function dbTaskToUITask(dbTask: Task): Task {
  return {
    ...dbTask,
    uiStatus: statusMappings.dbToUI[dbTask.status]
  };
}

// Helper function to convert UI status to database status  
export function uiStatusToDBStatus(uiStatus: UITaskStatus): DatabaseTaskStatus {
  return statusMappings.uiToDB[uiStatus];
} 