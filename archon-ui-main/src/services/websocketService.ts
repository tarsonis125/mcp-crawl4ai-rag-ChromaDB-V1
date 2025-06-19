/**
 * Socket.IO WebSocket Service
 * 
 * Features:
 * - Socket.IO for better reliability and reconnection
 * - Connection state management
 * - Promise-based connection establishment
 * - Automatic reconnection with exponential backoff
 * - Typed message handlers
 * - Support for dynamic endpoints
 * - Built-in heartbeat/keepalive
 * - Better error handling and recovery
 */

import { io, Socket } from 'socket.io-client';

export enum WebSocketState {
  CONNECTING = 'CONNECTING',
  CONNECTED = 'CONNECTED',
  RECONNECTING = 'RECONNECTING',
  DISCONNECTED = 'DISCONNECTED',
  FAILED = 'FAILED'
}

export interface WebSocketConfig {
  maxReconnectAttempts?: number;
  reconnectInterval?: number;
  heartbeatInterval?: number;
  messageTimeout?: number;
  enableHeartbeat?: boolean;
  enableAutoReconnect?: boolean;
}

export interface WebSocketMessage {
  type: string;
  data?: any;
  timestamp?: string;
  [key: string]: any;
}

type MessageHandler = (message: WebSocketMessage) => void;
type ErrorHandler = (error: Event | Error) => void;
type StateChangeHandler = (state: WebSocketState) => void;

export class WebSocketService {
  private socket: Socket | null = null;
  private config: Required<WebSocketConfig>;
  private namespace: string = '';
  private sessionId: string = '';
  
  private messageHandlers: Map<string, MessageHandler[]> = new Map();
  private errorHandlers: ErrorHandler[] = [];
  private stateChangeHandlers: StateChangeHandler[] = [];
  private connectionPromise: Promise<void> | null = null;
  private connectionResolver: (() => void) | null = null;
  private connectionRejector: ((error: Error) => void) | null = null;
  
  private _state: WebSocketState = WebSocketState.DISCONNECTED;

  constructor(config: WebSocketConfig = {}) {
    this.config = {
      maxReconnectAttempts: 5,
      reconnectInterval: 1000,
      heartbeatInterval: 30000,
      messageTimeout: 60000,
      enableHeartbeat: true,
      enableAutoReconnect: true,
      ...config
    };
  }

  get state(): WebSocketState {
    return this._state;
  }

  private setState(newState: WebSocketState): void {
    if (this._state !== newState) {
      this._state = newState;
      this.notifyStateChange(newState);
    }
  }

  /**
   * Connect to Socket.IO with promise-based connection establishment
   */
  async connect(endpoint: string): Promise<void> {
    // Extract namespace and session ID from endpoint
    const { namespace, sessionId } = this.parseEndpoint(endpoint);
    
    // If already connected to the same namespace and session, return existing connection
    if (this.socket && this.state === WebSocketState.CONNECTED && 
        this.namespace === namespace && this.sessionId === sessionId) {
      return Promise.resolve();
    }

    // If currently connecting, return existing promise
    if (this.connectionPromise && this.state === WebSocketState.CONNECTING) {
      return this.connectionPromise;
    }

    // Disconnect from current namespace if different
    if (this.socket && (this.namespace !== namespace || this.sessionId !== sessionId)) {
      this.disconnect();
    }

    this.namespace = namespace;
    this.sessionId = sessionId;
    this.setState(WebSocketState.CONNECTING);

    // Create connection promise
    this.connectionPromise = new Promise<void>((resolve, reject) => {
      this.connectionResolver = resolve;
      this.connectionRejector = reject;
    });

    try {
      await this.establishConnection();
      return this.connectionPromise;
    } catch (error) {
      this.setState(WebSocketState.FAILED);
      throw error;
    }
  }

  private parseEndpoint(endpoint: string): { namespace: string; sessionId: string } {
    // Extract session ID from endpoint
    const sessionMatch = endpoint.match(/sessions\/([^\/]+)/);
    const sessionId = sessionMatch ? sessionMatch[1] : '';
    
    // Extract project ID for task updates
    const projectMatch = endpoint.match(/projects\/([^\/]+)/);
    const projectId = projectMatch ? projectMatch[1] : '';
    
    // Map endpoints to Socket.IO namespaces
    let namespace = '/';
    if (endpoint.includes('/agent-chat/')) {
      namespace = '/chat';
    } else if (endpoint.includes('/crawl/')) {
      namespace = '/crawl';
    } else if (endpoint.includes('/projects/') && endpoint.includes('/tasks/')) {
      namespace = '/tasks';
    } else if (endpoint.includes('/projects/stream')) {
      namespace = '/project';
    } else if (endpoint.includes('/project-creation-progress/')) {
      namespace = '/project';
    }
    
    return { namespace, sessionId: sessionId || projectId };
  }

  private async establishConnection(): Promise<void> {
    // Use relative URL to go through Vite's proxy
    const socketPath = '/socket.io/';  // Use default Socket.IO path
    
    console.log(`🔌 Connecting to Socket.IO: ${this.namespace} namespace via proxy`);
    
    try {
      // Create Socket.IO connection with namespace
      this.socket = io(this.namespace, {
        reconnection: this.config.enableAutoReconnect,
        reconnectionAttempts: this.config.maxReconnectAttempts,
        reconnectionDelay: this.config.reconnectInterval,
        reconnectionDelayMax: 30000,
        timeout: 10000,
        transports: ['websocket', 'polling'],
        path: socketPath,
        query: {
          session_id: this.sessionId
        }
      });
      
      this.setupEventHandlers();
    } catch (error) {
      console.error('Failed to create Socket.IO connection:', error);
      if (this.connectionRejector) {
        this.connectionRejector(error as Error);
      }
    }
  }

  private setupEventHandlers(): void {
    if (!this.socket) return;

    this.socket.on('connect', () => {
      console.log(`✅ Socket.IO connected to ${this.namespace} namespace`);
      this.setState(WebSocketState.CONNECTED);
      
      // Emit session join event for chat namespace
      if (this.namespace === '/chat' && this.sessionId) {
        this.socket!.emit('join_session', { session_id: this.sessionId });
      }
      
      // Resolve connection promise
      if (this.connectionResolver) {
        this.connectionResolver();
        this.connectionResolver = null;
        this.connectionRejector = null;
      }
    });

    this.socket.on('disconnect', (reason: string) => {
      console.log(`🔌 Socket.IO disconnected from ${this.namespace}`, { reason });
      
      // Socket.IO handles reconnection automatically based on the reason
      if (reason === 'io server disconnect') {
        // Server initiated disconnect, won't auto-reconnect
        this.setState(WebSocketState.DISCONNECTED);
      } else {
        // Client side disconnect, will auto-reconnect
        this.setState(WebSocketState.RECONNECTING);
      }
      
      // Reject connection promise if still pending
      if (this.connectionRejector) {
        this.connectionRejector(new Error(`Socket disconnected: ${reason}`));
        this.connectionResolver = null;
        this.connectionRejector = null;
      }
    });

    this.socket.on('connect_error', (error: Error) => {
      console.error('Socket.IO connection error:', error);
      this.notifyError(error);
      
      // Reject connection promise if still pending
      if (this.connectionRejector) {
        this.connectionRejector(error);
        this.connectionResolver = null;
        this.connectionRejector = null;
      }
    });

    this.socket.on('reconnect', (attemptNumber: number) => {
      console.log(`🔄 Socket.IO reconnected after ${attemptNumber} attempts`);
      this.setState(WebSocketState.CONNECTED);
    });

    this.socket.on('reconnect_attempt', (attemptNumber: number) => {
      console.log(`🔄 Socket.IO reconnection attempt ${attemptNumber}`);
      this.setState(WebSocketState.RECONNECTING);
    });

    this.socket.on('reconnect_failed', () => {
      console.error('Socket.IO reconnection failed');
      this.setState(WebSocketState.FAILED);
    });

    // Handle incoming messages
    this.socket.onAny((eventName: string, ...args: any[]) => {
      // Skip internal Socket.IO events
      if (eventName.startsWith('connect') || eventName.startsWith('disconnect') || 
          eventName.startsWith('reconnect') || eventName === 'error') {
        return;
      }
      
      // Convert Socket.IO event to WebSocket message format
      const message: WebSocketMessage = {
        type: eventName,
        data: args[0],
        timestamp: new Date().toISOString()
      };
      
      // Handle specific message types
      if (eventName === 'message' && args[0]) {
        // Chat message format
        Object.assign(message, args[0]);
      }
      
      this.handleMessage(message);
    });
  }

  private handleMessage(message: WebSocketMessage): void {
    // Notify specific type handlers
    const handlers = this.messageHandlers.get(message.type) || [];
    handlers.forEach(handler => {
      try {
        handler(message);
      } catch (error) {
        console.error(`Error in message handler for type ${message.type}:`, error);
      }
    });
    
    // Notify wildcard handlers
    const wildcardHandlers = this.messageHandlers.get('*') || [];
    wildcardHandlers.forEach(handler => {
      try {
        handler(message);
      } catch (error) {
        console.error('Error in wildcard message handler:', error);
      }
    });
  }

  private notifyError(error: Event | Error): void {
    this.errorHandlers.forEach(handler => {
      try {
        handler(error);
      } catch (err) {
        console.error('Error in error handler:', err);
      }
    });
  }

  private notifyStateChange(state: WebSocketState): void {
    this.stateChangeHandlers.forEach(handler => {
      try {
        handler(state);
      } catch (error) {
        console.error('Error in state change handler:', error);
      }
    });
  }

  /**
   * Add message handler for specific message type
   * Use '*' to handle all message types
   */
  addMessageHandler(type: string, handler: MessageHandler): void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, []);
    }
    this.messageHandlers.get(type)!.push(handler);
  }

  removeMessageHandler(type: string, handler: MessageHandler): void {
    const handlers = this.messageHandlers.get(type);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
    }
  }

  addErrorHandler(handler: ErrorHandler): void {
    this.errorHandlers.push(handler);
  }

  removeErrorHandler(handler: ErrorHandler): void {
    const index = this.errorHandlers.indexOf(handler);
    if (index > -1) {
      this.errorHandlers.splice(index, 1);
    }
  }

  addStateChangeHandler(handler: StateChangeHandler): void {
    this.stateChangeHandlers.push(handler);
  }

  removeStateChangeHandler(handler: StateChangeHandler): void {
    const index = this.stateChangeHandlers.indexOf(handler);
    if (index > -1) {
      this.stateChangeHandlers.splice(index, 1);
    }
  }

  /**
   * Send a message via Socket.IO
   */
  send(data: any): boolean {
    if (!this.isConnected()) {
      console.warn('Cannot send message: Socket.IO not connected');
      return false;
    }
    
    try {
      // For Socket.IO, we emit events based on message type
      if (data.type) {
        this.socket!.emit(data.type, data.data || data);
      } else {
        // Default message event
        this.socket!.emit('message', data);
      }
      return true;
    } catch (error) {
      console.error('Failed to send message:', error);
      return false;
    }
  }

  /**
   * Wait for connection to be established
   */
  async waitForConnection(timeout: number = 10000): Promise<void> {
    if (this.isConnected()) {
      return Promise.resolve();
    }
    
    if (this.connectionPromise) {
      return this.connectionPromise;
    }
    
    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
        reject(new Error('Connection timeout'));
      }, timeout);
      
      const checkConnection = () => {
        if (this.isConnected()) {
          clearTimeout(timeoutId);
          resolve();
        } else if (this.state === WebSocketState.FAILED) {
          clearTimeout(timeoutId);
          reject(new Error('Connection failed'));
        } else {
          setTimeout(checkConnection, 100);
        }
      };
      
      checkConnection();
    });
  }

  isConnected(): boolean {
    return this.socket?.connected === true;
  }

  disconnect(): void {
    this.setState(WebSocketState.DISCONNECTED);
    
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    
    this.messageHandlers.clear();
    this.errorHandlers = [];
    this.stateChangeHandlers = [];
    this.namespace = '';
    this.sessionId = '';
    this.connectionPromise = null;
    this.connectionResolver = null;
    this.connectionRejector = null;
  }
}

// Export a factory function for creating instances with specific configurations
export function createWebSocketService(config?: WebSocketConfig): WebSocketService {
  return new WebSocketService(config);
}

// Export singleton instances for different features
export const knowledgeWebSocket = new WebSocketService();

// Export instances for backward compatibility
export const taskUpdateWebSocket = new WebSocketService();
export const projectListWebSocket = new WebSocketService();