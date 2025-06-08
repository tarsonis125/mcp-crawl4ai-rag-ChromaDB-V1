/**
 * Agent Chat Service
 * Handles communication with AI agents via REST API and WebSocket streaming
 */

interface ChatMessage {
  id: string;
  content: string;
  sender: 'user' | 'agent';
  timestamp: Date;
  agent_type?: string;
}

interface ChatSession {
  session_id: string;
  project_id?: string;
  messages: ChatMessage[];
  agent_type: string;
  created_at: Date;
}

interface ChatRequest {
  message: string;
  project_id?: string;
  context?: Record<string, any>;
}

interface WebSocketMessage {
  type: 'message' | 'typing' | 'ping' | 'stream_chunk' | 'stream_complete' | 'connection_confirmed' | 'heartbeat' | 'pong';
  data?: any;
  content?: string;
  session_id?: string;
  is_typing?: boolean;
}

class AgentChatService {
  private baseUrl: string;
  private wsConnections: Map<string, WebSocket> = new Map();
  private messageHandlers: Map<string, (message: ChatMessage) => void> = new Map();
  private typingHandlers: Map<string, (isTyping: boolean) => void> = new Map();
  private streamHandlers: Map<string, (chunk: string) => void> = new Map();
  private streamCompleteHandlers: Map<string, () => void> = new Map();
  private errorHandlers: Map<string, (error: Event) => void> = new Map();
  private closeHandlers: Map<string, (event: CloseEvent) => void> = new Map();
  private reconnectTimeouts: Map<string, NodeJS.Timeout> = new Map();
  private reconnectAttempts: Map<string, number> = new Map();
  private readonly maxReconnectAttempts = 5;
  private readonly reconnectDelay = 1000; // 1 second initial delay

  constructor() {
    this.baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8080';
  }

  /**
   * Get WebSocket URL for a session
   */
  private getWebSocketUrl(sessionId: string): string {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = new URL(this.baseUrl).host;
    return `${wsProtocol}//${host}/api/agent-chat/sessions/${sessionId}/ws`;
  }

  /**
   * Clean up WebSocket connection and handlers for a session
   */
  private cleanupConnection(sessionId: string): void {
    // Clear any pending reconnection attempt
    const reconnectTimeout = this.reconnectTimeouts.get(sessionId);
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      this.reconnectTimeouts.delete(sessionId);
    }
    
    // Close WebSocket if it exists
    const ws = this.wsConnections.get(sessionId);
    if (ws) {
      // Be more careful about closing connections
      if (ws.readyState === WebSocket.OPEN) {
        console.log(`Closing WebSocket connection for session ${sessionId}`);
        ws.close(1000, 'Client disconnected');
      } else if (ws.readyState === WebSocket.CONNECTING) {
        console.log(`Aborting connecting WebSocket for session ${sessionId}`);
        // For connecting sockets, we need to wait or force close
        ws.close();
      }
      this.wsConnections.delete(sessionId);
    }
    
    // Remove all handlers
    this.messageHandlers.delete(sessionId);
    this.typingHandlers.delete(sessionId);
    this.streamHandlers.delete(sessionId);
    this.streamCompleteHandlers.delete(sessionId);
    this.errorHandlers.delete(sessionId);
    this.closeHandlers.delete(sessionId);
    this.reconnectAttempts.delete(sessionId);
  }

  /**
   * Schedule a reconnection attempt with exponential backoff
   */
  private scheduleReconnect(sessionId: string): void {
    const attempts = this.reconnectAttempts.get(sessionId) || 0;
    
    if (attempts >= this.maxReconnectAttempts) {
      console.error(`Max reconnection attempts (${this.maxReconnectAttempts}) reached for session ${sessionId}`);
      this.cleanupConnection(sessionId);
      return;
    }

    const delay = this.reconnectDelay * Math.pow(2, attempts);
    console.log(`Attempting to reconnect in ${delay}ms (attempt ${attempts + 1}/${this.maxReconnectAttempts})`);
    
    const timeoutId = setTimeout(() => {
      if (this.reconnectTimeouts.has(sessionId)) {
        this.reconnectTimeouts.delete(sessionId);
        this.connectWebSocket(
          sessionId,
          this.messageHandlers.get(sessionId)!,
          this.typingHandlers.get(sessionId)!,
          this.streamHandlers.get(sessionId),
          this.streamCompleteHandlers.get(sessionId),
          this.errorHandlers.get(sessionId),
          this.closeHandlers.get(sessionId)
        );
      }
    }, delay);

    this.reconnectAttempts.set(sessionId, attempts + 1);
    this.reconnectTimeouts.set(sessionId, timeoutId);
  }

  /**
   * Handle incoming WebSocket messages
   */
  private handleIncomingMessage(
    event: MessageEvent,
    onMessage: (message: ChatMessage) => void,
    onTyping: (isTyping: boolean) => void,
    onStreamChunk?: (chunk: string) => void,
    onStreamComplete?: () => void
  ): void {
    try {
      const wsMessage = JSON.parse(event.data) as WebSocketMessage;
      
      switch (wsMessage.type) {
        case 'message':
          if (wsMessage.data) {
            // Ensure timestamp is a Date object
            if (typeof wsMessage.data.timestamp === 'string') {
              wsMessage.data.timestamp = new Date(wsMessage.data.timestamp);
            }
            onMessage(wsMessage.data);
          }
          break;
          
        case 'typing':
          // Handle both possible formats for typing status
          const isTyping = wsMessage.is_typing === true || 
                         (wsMessage.data && wsMessage.data.is_typing === true);
          onTyping(isTyping);
          break;
          
        case 'stream_chunk':
          if (onStreamChunk && wsMessage.content) {
            onStreamChunk(wsMessage.content);
          }
          break;
          
        case 'stream_complete':
          if (onStreamComplete) {
            onStreamComplete();
          }
          break;
          
        case 'ping':
          // Keep connection alive - no action needed
          break;
          
        case 'connection_confirmed':
          // Connection established successfully
          console.log('✅ Agent chat WebSocket connection confirmed');
          break;
          
        case 'heartbeat':
          // Server heartbeat - respond with ping
          console.log('💓 Received heartbeat from server');
          // Find the sessionId from the connection map
          const currentSessionId = wsMessage.session_id || Array.from(this.wsConnections.entries()).find(([_, ws]) => ws === event.target)?.[0];
          if (currentSessionId && this.wsConnections.get(currentSessionId)) {
            this.wsConnections.get(currentSessionId)?.send('ping');
          }
          break;
          
        case 'pong':
          // Response to our ping - connection is alive
          console.log('🏓 Received pong from server');
          break;
          
        default:
          console.warn('Unknown WebSocket message type:', wsMessage.type);
      }
    } catch (error) {
      console.error('Error processing WebSocket message:', error);
    }
  }

  /**
   * Create a new chat session with an agent
   */
  async createSession(projectId?: string, agentType: string = 'docs'): Promise<{ session_id: string }> {
    const response = await fetch(`${this.baseUrl}/api/agent-chat/sessions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        project_id: projectId,
        agent_type: agentType,
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to create chat session: ${response.statusText}`);
    }

    const data = await response.json();
    return { session_id: data.session_id || data.id };
  }

  /**
   * Get chat session details
   */
  async getSession(sessionId: string): Promise<ChatSession> {
    const response = await fetch(`${this.baseUrl}/api/agent-chat/sessions/${sessionId}`);

    if (!response.ok) {
      throw new Error(`Failed to get chat session: ${response.statusText}`);
    }

    const data = await response.json();
    
    // Handle different response formats
    const session = data.session || data;
    
    // Convert timestamps to Date objects
    if (typeof session.created_at === 'string') {
      session.created_at = new Date(session.created_at);
    }
    
    if (session.messages) {
      session.messages = session.messages.map((msg: any) => ({
        ...msg,
        timestamp: typeof msg.timestamp === 'string' ? new Date(msg.timestamp) : msg.timestamp
      }));
    }

    return session;
  }

  /**
   * Send a message in a chat session
   */
  async sendMessage(
    sessionId: string,
    message: string,
    context?: Record<string, any>
  ): Promise<void> {
    const chatRequest: ChatRequest = {
      message,
      context,
    };

    const response = await fetch(
      `${this.baseUrl}/api/agent-chat/sessions/${sessionId}/messages`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(chatRequest),
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to send message: ${response.statusText}`);
    }
  }

  /**
   * Connect to WebSocket for real-time communication
   */
  connectWebSocket(
    sessionId: string,
    onMessage: (message: ChatMessage) => void,
    onTyping: (isTyping: boolean) => void,
    onStreamChunk?: (chunk: string) => void,
    onStreamComplete?: () => void,
    onError?: (error: Event) => void,
    onClose?: (event: CloseEvent) => void
  ): void {
    // Check and close any existing connection properly
    const existingWs = this.wsConnections.get(sessionId);
    if (existingWs) {
      console.log(`🧹 Cleaning up existing WebSocket for session ${sessionId}, state: ${existingWs.readyState}`);
      // Always close existing connection regardless of state
      if (existingWs.readyState === WebSocket.OPEN || existingWs.readyState === WebSocket.CONNECTING) {
        existingWs.close(1000, 'Reconnecting');
      }
      this.wsConnections.delete(sessionId);
      
             // If it was still connecting, we'll just proceed - the close() call above will handle it
       if (existingWs.readyState === WebSocket.CONNECTING) {
         console.log(`⚠️ Previous connection was still connecting, forced close initiated`);
       }
    }

    // Store handlers for reconnection
    this.messageHandlers.set(sessionId, onMessage);
    this.typingHandlers.set(sessionId, onTyping);
    
    if (onStreamChunk) {
      this.streamHandlers.set(sessionId, onStreamChunk);
    }
    
    if (onStreamComplete) {
      this.streamCompleteHandlers.set(sessionId, onStreamComplete);
    }
    
    if (onError) {
      this.errorHandlers.set(sessionId, onError);
    }
    
    if (onClose) {
      this.closeHandlers.set(sessionId, onClose);
    }

    // Reset reconnect attempts
    this.reconnectAttempts.set(sessionId, 0);

    // Create WebSocket connection
    const wsUrl = this.getWebSocketUrl(sessionId);
    console.log(`🔌 Attempting to connect WebSocket to: ${wsUrl}`);
    
    const ws = new WebSocket(wsUrl);
    this.wsConnections.set(sessionId, ws);

    ws.onopen = () => {
      console.log(`🚀 WebSocket connected for session ${sessionId}`);
      // Reset reconnect attempts on successful connection
      this.reconnectAttempts.set(sessionId, 0);
    };

    ws.onmessage = (event) => {
      console.log(`📨 WebSocket message received for session ${sessionId}:`, event.data);
      this.handleIncomingMessage(
        event,
        onMessage,
        onTyping,
        onStreamChunk,
        onStreamComplete
      );
    };

    ws.onerror = (error) => {
      console.error(`❌ WebSocket error for session ${sessionId}:`, error);
      console.error(`WebSocket state at error: ${ws.readyState} (0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED)`);
      if (onError) {
        onError(error);
      }
    };

    ws.onclose = (event) => {
      console.log(`🔌 WebSocket closed for session ${sessionId}:`, event.code, event.reason);
      console.log(`Close event details: wasClean=${event.wasClean}, code=${event.code}`);
      this.wsConnections.delete(sessionId);
      
      // Only try to reconnect if this wasn't an intentional close
      if (event.code !== 1000) { // 1000 is normal closure
        console.log(`Scheduling reconnect for abnormal closure (code ${event.code})`);
        this.scheduleReconnect(sessionId);
      }
      
      if (onClose) {
        onClose(event);
      }
    };
  }

  /**
   * Disconnect WebSocket for a session
   */
  disconnectWebSocket(sessionId: string): void {
    this.cleanupConnection(sessionId);
  }

  /**
   * Disconnect all WebSocket connections
   */
  disconnectAll(): void {
    this.wsConnections.forEach((_, sessionId) => {
      this.disconnectWebSocket(sessionId);
    });
  }

  /**
   * Check if WebSocket is connected for a session
   */
  isConnected(sessionId: string): boolean {
    const ws = this.wsConnections.get(sessionId);
    return ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Get WebSocket connection state for a session
   */
  getConnectionState(sessionId: string): number | null {
    const ws = this.wsConnections.get(sessionId);
    return ws?.readyState ?? null;
  }
}

// Export singleton instance
export const agentChatService = new AgentChatService();
export type { ChatMessage, ChatSession, ChatRequest };
