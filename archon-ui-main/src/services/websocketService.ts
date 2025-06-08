class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectInterval = 1000;
  private listeners: Map<string, Function[]> = new Map();

  connect(endpoint: string) {
    // Use the current host but with the backend port
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const port = '8080'; // Backend WebSocket port
    const wsUrl = `${protocol}//${host}:${port}${endpoint}`;
    
    console.log(`Connecting to WebSocket: ${wsUrl}`);
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      console.log(`WebSocket connected to ${endpoint}`);
      this.reconnectAttempts = 0;
    };
    
    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleMessage(data);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };
    
    this.ws.onclose = () => {
      console.log(`WebSocket disconnected from ${endpoint}`);
      this.attemptReconnect(endpoint);
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }
  
  private attemptReconnect(endpoint: string) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      setTimeout(() => {
        console.log(`Attempting to reconnect... (${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);
        this.reconnectAttempts++;
        this.connect(endpoint);
      }, this.reconnectInterval * Math.pow(2, this.reconnectAttempts));
    }
  }
  
  private handleMessage(data: any) {
    const listeners = this.listeners.get(data.type) || [];
    listeners.forEach(listener => {
      try {
        listener(data);
      } catch (error) {
        console.error('Error in WebSocket message listener:', error);
      }
    });
  }
  
  addEventListener(type: string, listener: Function) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type)!.push(listener);
  }
  
  removeEventListener(type: string, listener: Function) {
    const listeners = this.listeners.get(type);
    if (listeners) {
      const index = listeners.indexOf(listener);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }
  
  send(data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
  
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.listeners.clear();
  }
}

// Export singleton instances
export const knowledgeWebSocket = new WebSocketService();
export const crawlWebSocket = new WebSocketService();

// Task Update WebSocket Service for real-time task updates
interface TaskUpdateData {
  type: 'task_created' | 'task_updated' | 'task_deleted' | 'task_archived' | 'connection_established';
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
  onError?: (error: Event) => void;
  onClose?: (event: CloseEvent) => void;
}

class TaskUpdateService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectInterval = 3000;
  private projectId: string | null = null;
  private callbacks: TaskUpdateCallbacks = {};

  connect(projectId: string, callbacks: TaskUpdateCallbacks) {
    this.projectId = projectId;
    this.callbacks = callbacks;
    
    // Use the current host but with the backend port
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const port = '8080'; // Backend WebSocket port
    const wsUrl = `${protocol}//${host}:${port}/api/projects/${projectId}/tasks/updates`;
    
    console.log(`🔌 Connecting to Task Updates WebSocket: ${wsUrl}`);
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      console.log(`🚀 Task Updates WebSocket connected for project: ${projectId}`);
      this.reconnectAttempts = 0;
    };
    
    this.ws.onmessage = (event) => {
      try {
        const data: TaskUpdateData = JSON.parse(event.data);
        console.log(`📨 Task update received:`, data);
        this.handleMessage(data);
      } catch (error) {
        console.error('Failed to parse Task Update WebSocket message:', error);
      }
    };
    
    this.ws.onclose = (event) => {
      console.log(`🔌 Task Updates WebSocket disconnected for project: ${projectId}`, event);
      this.attemptReconnect();
      
      if (this.callbacks.onClose) {
        this.callbacks.onClose(event);
      }
    };
    
    this.ws.onerror = (error) => {
      console.error('Task Updates WebSocket error:', error);
      
      if (this.callbacks.onError) {
        this.callbacks.onError(error);
      }
    };
  }

  private handleMessage(data: TaskUpdateData) {
    switch (data.type) {
      case 'connection_established':
        console.log('🎯 Task updates connection established');
        if (this.callbacks.onConnectionEstablished) {
          this.callbacks.onConnectionEstablished();
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
        
      default:
        console.warn('Unknown task update message type:', data.type);
    }
  }

  private attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts && this.projectId) {
      this.reconnectAttempts++;
      console.log(`🔄 Attempting to reconnect Task Updates WebSocket (${this.reconnectAttempts}/${this.maxReconnectAttempts}) in ${this.reconnectInterval}ms`);
      
      setTimeout(() => {
        if (this.projectId) {
          this.connect(this.projectId, this.callbacks);
        }
      }, this.reconnectInterval);
    } else {
      console.error('❌ Max reconnection attempts reached for Task Updates WebSocket');
    }
  }

  sendPing() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send('ping');
    }
  }

  disconnect() {
    if (this.ws) {
      console.log('🔌 Disconnecting Task Updates WebSocket');
      this.ws.close(1000, 'Client disconnecting');
      this.ws = null;
    }
    this.projectId = null;
    this.callbacks = {};
    this.reconnectAttempts = 0;
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// Export singleton instances
export const taskUpdateWebSocket = new TaskUpdateService(); 