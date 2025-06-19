import {
  EnhancedWebSocketService,
  createWebSocketService,
  WebSocketState,
  WebSocketMessage
} from './EnhancedWebSocketService';

/**
 * WebSocket-Safe Threading Utilities
 * Provides patterns for parallel processing that don't block WebSocket event loops
 */

// Progress callback type for long-running operations
export type ProgressCallback = (completed: number, total: number, message?: string) => void;
export type WebSocketProgressCallback = (websocket: any, completed: number, total: number, message?: string) => void;

// Rate limiter with semaphore-like behavior
class RateLimiter {
  private tokens: number;
  private maxTokens: number;
  private refillRate: number;
  private lastRefill: number;

  constructor(maxTokens: number = 5, refillRate: number = 1000) {
    this.maxTokens = maxTokens;
    this.tokens = maxTokens;
    this.refillRate = refillRate; // ms between token refills
    this.lastRefill = Date.now();
  }

  private refillTokens(): void {
    const now = Date.now();
    const timePassed = now - this.lastRefill;
    const tokensToAdd = Math.floor(timePassed / this.refillRate);
    
    if (tokensToAdd > 0) {
      this.tokens = Math.min(this.maxTokens, this.tokens + tokensToAdd);
      this.lastRefill = now;
    }
  }

  async waitForToken(): Promise<void> {
    this.refillTokens();
    
    if (this.tokens > 0) {
      this.tokens--;
      return Promise.resolve();
    }
    
    // Wait for next token
    const waitTime = this.refillRate - (Date.now() - this.lastRefill);
    await new Promise(resolve => setTimeout(resolve, Math.max(0, waitTime)));
    return this.waitForToken();
  }
}

/**
 * WebSocket-Safe Threading Utilities
 */
export class WebSocketThreadingUtils {
  private static rateLimiter = new RateLimiter(5, 200); // 5 tokens, refill every 200ms

  /**
   * Process items in parallel with WebSocket-safe yielding
   * Prevents blocking the event loop while maintaining progress updates
   */
  static async processParallel<T, R>(
    items: T[],
    processor: (item: T) => Promise<R> | R,
    options: {
      maxConcurrency?: number;
      batchSize?: number;
      yieldInterval?: number;
      progressCallback?: ProgressCallback;
      websocket?: any;
      websocketProgressCallback?: WebSocketProgressCallback;
    } = {}
  ): Promise<R[]> {
    const {
      maxConcurrency = 3,
      batchSize = 10,
      yieldInterval = 5,
      progressCallback,
      websocket,
      websocketProgressCallback
    } = options;

    const results: R[] = [];
    let completed = 0;

    // Process in batches to avoid overwhelming
    for (let i = 0; i < items.length; i += batchSize) {
      const batch = items.slice(i, i + batchSize);
      
      // Process batch with limited concurrency
      const batchPromises = batch.map(async (item, index) => {
        // Rate limiting
        await this.rateLimiter.waitForToken();
        
        // Process item
        const result = await processor(item);
        completed++;
        
        // Yield control periodically to prevent event loop blocking
        if (index % yieldInterval === 0) {
          await this.yieldControl();
        }
        
        // Progress updates
        if (progressCallback) {
          progressCallback(completed, items.length);
        }
        
        if (websocket && websocketProgressCallback) {
          websocketProgressCallback(websocket, completed, items.length);
        }
        
        return result;
      });

      // Wait for batch completion with concurrency limit
      const semaphore = new Array(maxConcurrency).fill(null);
      const batchResults: R[] = [];
      
      for (let j = 0; j < batchPromises.length; j += maxConcurrency) {
        const concurrentBatch = batchPromises.slice(j, j + maxConcurrency);
        const concurrentResults = await Promise.all(concurrentBatch);
        batchResults.push(...concurrentResults);
        
        // Yield after each concurrent batch
        await this.yieldControl();
      }
      
      results.push(...batchResults);
      
      // Send batch completion update
      if (websocket) {
        websocket.send(JSON.stringify({
          type: 'batch_complete',
          completed,
          total: items.length,
          batch_size: batch.length
        }));
      }
    }

    return results;
  }

  /**
   * Run CPU-intensive work in a way that doesn't block WebSocket
   * Uses setTimeout to break up work and yield control
   */
  static async runCpuIntensiveTask<T>(
    task: () => T | Promise<T>,
    options: {
      yieldInterval?: number;
      progressCallback?: ProgressCallback;
      websocket?: any;
      taskName?: string;
    } = {}
  ): Promise<T> {
    const { yieldInterval = 100, progressCallback, websocket, taskName = 'task' } = options;
    
    if (websocket) {
      websocket.send(JSON.stringify({
        type: 'task_started',
        task_name: taskName,
        timestamp: new Date().toISOString()
      }));
    }
    
    // Yield control before starting
    await this.yieldControl();
    
    try {
      const result = await task();
      
      if (websocket) {
        websocket.send(JSON.stringify({
          type: 'task_completed',
          task_name: taskName,
          timestamp: new Date().toISOString()
        }));
      }
      
      return result;
    } catch (error) {
      if (websocket) {
        websocket.send(JSON.stringify({
          type: 'task_error',
          task_name: taskName,
          error: error instanceof Error ? error.message : String(error),
          timestamp: new Date().toISOString()
        }));
      }
      throw error;
    }
  }

  /**
   * Process items with automatic rate limiting and progress updates
   */
  static async processWithRateLimit<T, R>(
    items: T[],
    processor: (item: T) => Promise<R> | R,
    options: {
      rateLimit?: number; // ms between requests
      maxConcurrency?: number;
      progressCallback?: ProgressCallback;
      websocket?: any;
      taskName?: string;
    } = {}
  ): Promise<R[]> {
    const {
      rateLimit = 100,
      maxConcurrency = 3,
      progressCallback,
      websocket,
      taskName = 'rate_limited_processing'
    } = options;

    const results: R[] = [];
    let completed = 0;

    if (websocket) {
      websocket.send(JSON.stringify({
        type: 'processing_started',
        task_name: taskName,
        total_items: items.length,
        rate_limit: rateLimit,
        max_concurrency: maxConcurrency
      }));
    }

    // Create semaphore for concurrency control
    const semaphore = new Array(maxConcurrency).fill(null);
    const processItem = async (item: T): Promise<R> => {
      // Rate limiting delay
      await new Promise(resolve => setTimeout(resolve, rateLimit));
      
      // Process item
      const result = await processor(item);
      completed++;
      
      // Progress update
      if (progressCallback) {
        progressCallback(completed, items.length);
      }
      
      if (websocket) {
        websocket.send(JSON.stringify({
          type: 'processing_progress',
          task_name: taskName,
          completed,
          total: items.length,
          progress_percent: Math.round((completed / items.length) * 100)
        }));
      }
      
      // Yield control
      await this.yieldControl();
      
      return result;
    };

    // Process with concurrency control
    for (let i = 0; i < items.length; i += maxConcurrency) {
      const batch = items.slice(i, i + maxConcurrency);
      const batchPromises = batch.map(processItem);
      const batchResults = await Promise.all(batchPromises);
      results.push(...batchResults);
    }

    if (websocket) {
      websocket.send(JSON.stringify({
        type: 'processing_completed',
        task_name: taskName,
        total_processed: results.length
      }));
    }

    return results;
  }

  /**
   * Yield control back to the event loop
   * Critical for preventing WebSocket blocking
   */
  static async yieldControl(): Promise<void> {
    await new Promise(resolve => setTimeout(resolve, 0));
  }

  /**
   * Create a background worker that processes items from a queue
   * Designed to work with WebSocket progress updates
   */
  static createBackgroundWorker<T, R>(
    processor: (item: T) => Promise<R> | R,
    options: {
      maxConcurrency?: number;
      yieldInterval?: number;
      websocket?: any;
      workerName?: string;
    } = {}
  ): {
    addWork: (item: T) => Promise<R>;
    getQueueSize: () => number;
    stop: () => void;
  } {
    const {
      maxConcurrency = 3,
      yieldInterval = 5,
      websocket,
      workerName = 'background_worker'
    } = options;

    const workQueue: Array<{
      item: T;
      resolve: (result: R) => void;
      reject: (error: any) => void;
    }> = [];

    let isRunning = true;
    let activeWorkers = 0;

    const processWork = async (): Promise<void> => {
      while (isRunning && workQueue.length > 0) {
        if (activeWorkers >= maxConcurrency) {
          await new Promise(resolve => setTimeout(resolve, 10));
          continue;
        }

        const work = workQueue.shift();
        if (!work) continue;

        activeWorkers++;
        
        try {
          const result = await processor(work.item);
          work.resolve(result);
          
          if (websocket) {
            websocket.send(JSON.stringify({
              type: 'worker_item_completed',
              worker_name: workerName,
              queue_size: workQueue.length,
              active_workers: activeWorkers
            }));
          }
        } catch (error) {
          work.reject(error);
          
          if (websocket) {
            websocket.send(JSON.stringify({
              type: 'worker_item_error',
              worker_name: workerName,
              error: error instanceof Error ? error.message : String(error),
              queue_size: workQueue.length
            }));
          }
        } finally {
          activeWorkers--;
          
          // Yield control periodically
          if (workQueue.length % yieldInterval === 0) {
            await this.yieldControl();
          }
        }
      }
    };

    // Start the worker
    processWork();

    return {
      addWork: (item: T): Promise<R> => {
        return new Promise((resolve, reject) => {
          workQueue.push({ item, resolve, reject });
          
          if (websocket) {
            websocket.send(JSON.stringify({
              type: 'worker_item_queued',
              worker_name: workerName,
              queue_size: workQueue.length
            }));
          }
          
          // Restart processing if needed
          if (isRunning && activeWorkers === 0) {
            processWork();
          }
        });
      },
      
      getQueueSize: () => workQueue.length,
      
      stop: () => {
        isRunning = false;
        
        if (websocket) {
          websocket.send(JSON.stringify({
            type: 'worker_stopped',
            worker_name: workerName
          }));
        }
      }
    };
  }
}

/**
 * Enhanced WebSocket Service Wrapper
 * Provides backward compatibility while using the new EnhancedWebSocketService
 */
class WebSocketService {
  private enhancedService: EnhancedWebSocketService;
  
  constructor() {
    this.enhancedService = createWebSocketService({
      maxReconnectAttempts: 5,
      reconnectInterval: 1000,
      heartbeatInterval: 30000,
      enableAutoReconnect: true
    });
  }

  async connect(endpoint: string): Promise<void> {
    console.log(`Connecting to WebSocket endpoint: ${endpoint}`);
    await this.enhancedService.connect(endpoint);
  }
  
  addEventListener(type: string, listener: Function) {
    this.enhancedService.addMessageHandler(type, (message) => {
      listener(message);
    });
  }
  
  removeEventListener(type: string, listener: Function) {
    // Note: EnhancedWebSocketService doesn't support removing specific handlers by reference
    // This is a limitation of the migration
    console.warn('removeEventListener not fully supported in migration');
  }
  
  send(data: any) {
    this.enhancedService.send(data);
  }
  
  disconnect() {
    this.enhancedService.disconnect();
  }

  isConnected(): boolean {
    return this.enhancedService.isConnected();
  }

  /**
   * WebSocket-safe parallel processing utilities
   */
  async processParallel<T, R>(
    items: T[],
    processor: (item: T) => Promise<R> | R,
    options: {
      maxConcurrency?: number;
      batchSize?: number;
      progressUpdates?: boolean;
      taskName?: string;
    } = {}
  ): Promise<R[]> {
    const websocketProgressCallback: WebSocketProgressCallback | undefined = options.progressUpdates 
      ? (ws, completed, total, message) => {
          this.send(JSON.stringify({
            type: 'processing_progress',
            task_name: options.taskName || 'parallel_processing',
            completed,
            total,
            progress_percent: Math.round((completed / total) * 100),
            message
          }));
        }
      : undefined;

    return WebSocketThreadingUtils.processParallel(items, processor, {
      ...options,
      websocket: this,
      websocketProgressCallback
    });
  }

  async runCpuIntensiveTask<T>(
    task: () => T | Promise<T>,
    options: {
      taskName?: string;
      progressUpdates?: boolean;
    } = {}
  ): Promise<T> {
    return WebSocketThreadingUtils.runCpuIntensiveTask(task, {
      ...options,
      websocket: options.progressUpdates ? this : undefined
    });
  }

  createBackgroundWorker<T, R>(
    processor: (item: T) => Promise<R> | R,
    options: {
      maxConcurrency?: number;
      workerName?: string;
      progressUpdates?: boolean;
    } = {}
  ) {
    return WebSocketThreadingUtils.createBackgroundWorker(processor, {
      ...options,
      websocket: options.progressUpdates ? this : undefined
    });
  }
}

// Export singleton instances
export const knowledgeWebSocket = new WebSocketService();
export const crawlWebSocket = new WebSocketService();
export const projectListWebSocket = new WebSocketService();
export const healthWebSocket = new WebSocketService();

// Task Update WebSocket Service for real-time task updates
interface TaskUpdateData {
  type: 'task_created' | 'task_updated' | 'task_deleted' | 'task_archived' | 'connection_established' | 'initial_tasks' | 'tasks_updated' | 'heartbeat' | 'pong';
  data: any;
  timestamp: string;
  project_id: string;
}

interface TaskUpdateCallbacks {
  onTaskCreated?: (task: any) => void;
  onTaskUpdated?: (task: any) => void;
  onTaskDeleted?: (task: any) => void;
  onTaskArchived?: (task: any) => void;
  onConnectionEstablished?: () => void;
  onInitialTasks?: (tasks: any[]) => void;
  onTasksChange?: (tasks: any[]) => void;
  onError?: (error: Event | Error) => void;
  onClose?: (event: CloseEvent) => void;
}

class TaskUpdateService {
  private enhancedService: EnhancedWebSocketService;
  private projectId: string | null = null;
  private sessionId: string | null = null;
  private callbacks: TaskUpdateCallbacks = {};

  constructor() {
    this.enhancedService = createWebSocketService({
      maxReconnectAttempts: 3,
      reconnectInterval: 5000,
      heartbeatInterval: 30000,
      enableAutoReconnect: true,
      enableHeartbeat: true
    });
  }

  async connect(projectId: string, callbacks: TaskUpdateCallbacks, sessionId?: string): Promise<void> {
    // Disconnect any existing connection
    if (this.isConnected()) {
      console.log('🔄 Closing existing WebSocket connection before creating new one');
      this.disconnect();
    }

    this.projectId = projectId;
    this.sessionId = sessionId || this.generateSessionId();
    this.callbacks = callbacks;
    
    // Include session ID as query parameter
    const endpoint = `/api/projects/${projectId}/tasks/ws?session_id=${this.sessionId}`;
    
    console.log(`🔌 Connecting to Task Updates WebSocket: ${endpoint}`);
    
    // Set up message handlers before connecting
    this.setupMessageHandlers();
    
    // Set up error handler
    if (callbacks.onError) {
      this.enhancedService.addErrorHandler(callbacks.onError);
    }
    
    // Set up state change handler for close events
    this.enhancedService.addStateChangeHandler((state) => {
      if (state === WebSocketState.DISCONNECTED && callbacks.onClose) {
        callbacks.onClose(new CloseEvent('close'));
      }
    });
    
    try {
      await this.enhancedService.connect(endpoint);
      console.log(`🔌 Task Updates WebSocket connected for project: ${projectId}, session: ${this.sessionId}`);
    } catch (error) {
      console.error('Failed to connect Task Updates WebSocket:', error);
      throw error;
    }
  }

  private generateSessionId(): string {
    return 'task-session-' + Math.random().toString(36).substr(2, 9);
  }

  private setupMessageHandlers(): void {
    // Handle all message types
    this.enhancedService.addMessageHandler('*', (message: WebSocketMessage) => {
      const data = message as TaskUpdateData;
      console.log(`📨 Task update received for session ${this.sessionId}:`, data);
      
      switch (data.type) {
        case 'connection_established':
          console.log('🎯 Task updates connection established');
          if (this.callbacks.onConnectionEstablished) {
            this.callbacks.onConnectionEstablished();
          }
          break;
          
        case 'initial_tasks':
          console.log('📋 Initial tasks received:', data.data);
          if (this.callbacks.onInitialTasks) {
            this.callbacks.onInitialTasks(data.data.tasks || []);
          }
          break;
          
        case 'tasks_updated':
          console.log('🔄 Tasks updated via MCP:', data.data);
          if (this.callbacks.onTasksChange) {
            this.callbacks.onTasksChange(data.data.updated_tasks || []);
          }
          break;
          
        case 'task_created':
          console.log('🆕 Task created:', data.data);
          if (this.callbacks.onTaskCreated) {
            this.callbacks.onTaskCreated(data.data);
          }
          break;
          
        case 'task_updated':
          console.log('📝 Task updated:', data.data);
          if (this.callbacks.onTaskUpdated) {
            this.callbacks.onTaskUpdated(data.data);
          }
          break;
          
        case 'task_deleted':
          console.log('🗑️ Task deleted:', data.data);
          if (this.callbacks.onTaskDeleted) {
            this.callbacks.onTaskDeleted(data.data);
          }
          break;
          
        case 'task_archived':
          console.log('📦 Task archived:', data.data);
          if (this.callbacks.onTaskArchived) {
            this.callbacks.onTaskArchived(data.data);
          }
          break;
          
        case 'heartbeat':
          console.log('💓 Heartbeat received from server');
          // Send ping response  
          this.sendPing();
          break;
          
        case 'pong':
          console.log('🏓 Pong received from server');
          // Connection is alive
          break;
          
        default:
          console.warn('Unknown task update message type:', data.type);
      }
    });
  }

  sendPing(): void {
    this.enhancedService.send('ping');
  }

  disconnect(): void {
    console.log(`🔌 Disconnecting Task Updates WebSocket`);
    this.enhancedService.disconnect();
    this.projectId = null;
    this.sessionId = null;
    this.callbacks = {};
  }

  isConnected(): boolean {
    return this.enhancedService.isConnected();
  }
}

// Export singleton instances
export const taskUpdateWebSocket = new TaskUpdateService(); 