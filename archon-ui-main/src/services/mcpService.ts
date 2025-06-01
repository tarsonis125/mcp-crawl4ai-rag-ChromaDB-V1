export interface ServerStatus {
  status: 'running' | 'starting' | 'stopped' | 'stopping';
  uptime: number | null;
  logs: string[];
}

export interface ServerResponse {
  success: boolean;
  status: string;
  message: string;
}

export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

export interface ServerConfig {
  transport: string;
  host: string;
  port: number;
  model?: string;
}

interface StreamLogOptions {
  autoReconnect?: boolean;
  reconnectDelay?: number;
}

class MCPService {
  private baseUrl = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8080';
  private wsUrl = this.baseUrl.replace('http', 'ws');
  private logWebSocket: WebSocket | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  public isReconnecting = false;

  async startServer(): Promise<ServerResponse> {
    const response = await fetch(`${this.baseUrl}/api/mcp/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to start MCP server');
    }

    return response.json();
  }

  async stopServer(): Promise<ServerResponse> {
    const response = await fetch(`${this.baseUrl}/api/mcp/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to stop MCP server');
    }

    return response.json();
  }

  async getStatus(): Promise<ServerStatus> {
    const response = await fetch(`${this.baseUrl}/api/mcp/status`);

    if (!response.ok) {
      throw new Error('Failed to get server status');
    }

    return response.json();
  }

  async getConfiguration(): Promise<ServerConfig> {
    const response = await fetch(`${this.baseUrl}/api/mcp/config`);

    if (!response.ok) {
      // Return default config if endpoint doesn't exist yet
      return {
        transport: 'sse',
        host: 'localhost',
        port: 8051
      };
    }

    return response.json();
  }

  async updateConfiguration(config: Partial<ServerConfig>): Promise<ServerResponse> {
    const response = await fetch(`${this.baseUrl}/api/mcp/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to update configuration');
    }

    return response.json();
  }

  async getLogs(options: { limit?: number } = {}): Promise<LogEntry[]> {
    const params = new URLSearchParams();
    if (options.limit) {
      params.append('limit', options.limit.toString());
    }

    const response = await fetch(`${this.baseUrl}/api/mcp/logs?${params}`);

    if (!response.ok) {
      throw new Error('Failed to fetch logs');
    }

    return response.json();
  }

  async clearLogs(): Promise<ServerResponse> {
    const response = await fetch(`${this.baseUrl}/api/mcp/logs`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' }
    });

    if (!response.ok) {
      throw new Error('Failed to clear logs');
    }

    return response.json();
  }

  streamLogs(
    onMessage: (log: LogEntry) => void,
    options: StreamLogOptions = {}
  ): WebSocket {
    const { autoReconnect = false, reconnectDelay = 5000 } = options;

    // Close existing connection if any
    this.disconnectLogs();

    const ws = new WebSocket(`${this.wsUrl}/api/mcp/logs/stream`);
    this.logWebSocket = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Ignore ping messages
        if (data.type === 'ping') {
          return;
        }

        // Handle log entries
        if (data.timestamp && data.level && data.message) {
          onMessage(data as LogEntry);
        }
      } catch (error) {
        console.error('Failed to parse log message:', error);
      }
    };

    ws.onclose = () => {
      this.logWebSocket = null;
      
      if (autoReconnect && !this.isReconnecting) {
        this.isReconnecting = true;
        this.reconnectTimeout = setTimeout(() => {
          this.isReconnecting = false;
          this.streamLogs(onMessage, options);
        }, reconnectDelay);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return ws;
  }

  disconnectLogs(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    
    this.isReconnecting = false;

    if (this.logWebSocket) {
      this.logWebSocket.close();
      this.logWebSocket = null;
    }
  }
}

export const mcpService = new MCPService(); 