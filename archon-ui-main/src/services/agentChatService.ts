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
  type: 'message' | 'typing' | 'ping' | 'stream_chunk' | 'stream_complete';
  data?: any;
  content?: string;
  session_id?: string;
}

class AgentChatService {
  private baseUrl: string;
  private wsConnections: Map<string, WebSocket> = new Map();
  private messageHandlers: Map<string, (message: ChatMessage) => void> = new Map();
  private typingHandlers: Map<string, (isTyping: boolean) => void> = new Map();

  constructor() {
    // Use the same pattern as projectService - backend is on port 8080
    this.baseUrl = 'http://localhost:8080';
  }

  /**
   * Create a new chat session with an agent
   */
  async createSession(
    projectId?: string, 
    agentType: string = 'docs'
  ): Promise<{ session_id: string }> {
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
    return { session_id: data.session_id };
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
    
    // Convert timestamp strings back to Date objects
    const session = data.session;
    session.created_at = new Date(session.created_at);
    session.messages = session.messages.map((msg: any) => ({
      ...msg,
      timestamp: new Date(msg.timestamp)
    }));

    return session;
  }

  /**
   * Send a message to an agent
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

    const response = await fetch(`${this.baseUrl}/api/agent-chat/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(chatRequest),
    });

    if (!response.ok) {
      throw new Error(`Failed to send message: ${response.statusText}`);
    }
  }

  /**
   * Connect to WebSocket for real-time chat
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
    // Close existing connection if any
    this.disconnectWebSocket(sessionId);

    const wsUrl = this.baseUrl.replace('http://', 'ws://').replace('https://', 'wss://');
    const ws = new WebSocket(`${wsUrl}/api/agent-chat/sessions/${sessionId}/ws`);

    ws.onopen = () => {
      console.log(`WebSocket connected for session ${sessionId}`);
    };

    ws.onmessage = (event) => {
      try {
        const wsMessage: WebSocketMessage = JSON.parse(event.data);
        
        switch (wsMessage.type) {
          case 'message':
            const message = wsMessage.data;
            // Convert timestamp string back to Date
            message.timestamp = new Date(message.timestamp);
            onMessage(message);
            break;
            
          case 'typing':
            onTyping(wsMessage.data.is_typing);
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
            
          default:
            console.log('Unknown WebSocket message type:', wsMessage.type);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error(`WebSocket error for session ${sessionId}:`, error);
      onError?.(error);
    };

    ws.onclose = (event) => {
      console.log(`WebSocket closed for session ${sessionId}:`, event.code, event.reason);
      this.wsConnections.delete(sessionId);
      onClose?.(event);
    };

    this.wsConnections.set(sessionId, ws);
    this.messageHandlers.set(sessionId, onMessage);
    this.typingHandlers.set(sessionId, onTyping);
  }

  /**
   * Disconnect WebSocket for a session
   */
  disconnectWebSocket(sessionId: string): void {
    const ws = this.wsConnections.get(sessionId);
    if (ws) {
      ws.close();
      this.wsConnections.delete(sessionId);
      this.messageHandlers.delete(sessionId);
      this.typingHandlers.delete(sessionId);
    }
  }

  /**
   * Disconnect all WebSocket connections
   */
  disconnectAll(): void {
    this.wsConnections.forEach((ws, sessionId) => {
      ws.close();
    });
    this.wsConnections.clear();
    this.messageHandlers.clear();
    this.typingHandlers.clear();
  }

  /**
   * Check if WebSocket is connected for a session
   */
  isConnected(sessionId: string): boolean {
    const ws = this.wsConnections.get(sessionId);
    return ws ? ws.readyState === WebSocket.OPEN : false;
  }

  /**
   * Get current WebSocket state for a session
   */
  getConnectionState(sessionId: string): number | null {
    const ws = this.wsConnections.get(sessionId);
    return ws ? ws.readyState : null;
  }
}

// Export singleton instance
export const agentChatService = new AgentChatService();
export type { ChatMessage, ChatSession, ChatRequest }; 