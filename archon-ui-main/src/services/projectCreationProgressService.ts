export interface ProjectCreationProgressData {
  progressId: string;
  status: 'starting' | 'initializing_agents' | 'generating_docs' | 'processing_requirements' | 'ai_generation' | 'finalizing_docs' | 'saving_to_database' | 'completed' | 'error';
  percentage: number;
  step?: string;
  currentStep?: string;
  eta?: string;
  error?: string;
  logs: string[];
  project?: any; // The created project when completed
  duration?: string;
}

interface StreamProgressOptions {
  autoReconnect?: boolean;
  reconnectDelay?: number;
}

type ProgressCallback = (data: ProjectCreationProgressData) => void;

class ProjectCreationProgressService {
  private baseUrl: string;
  private wsUrl: string;

  constructor() {
    this.baseUrl = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8080';
    this.wsUrl = this.baseUrl.replace('http', 'ws');
  }
  private progressWebSocket: WebSocket | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  public isReconnecting = false;

  /**
   * Stream project creation progress similar to how MCP logs and crawl progress work
   */
  streamProgress(
    progressId: string,
    onMessage: ProgressCallback,
    options: StreamProgressOptions = {}
  ): WebSocket {
    const { autoReconnect = true, reconnectDelay = 5000 } = options;

    // Close existing connection if any
    this.disconnect();

    const ws = new WebSocket(`${this.wsUrl}/api/project-creation-progress/${progressId}`);
    this.progressWebSocket = ws;

    ws.onopen = () => {
      console.log(`🚀 Connected to project creation progress stream: ${progressId}`);
      this.isReconnecting = false;
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        
        // Ignore ping messages
        if (message.type === 'ping') {
          return;
        }

        // Handle progress messages
        if (message.type === 'project_progress' || message.type === 'project_completed' || message.type === 'project_error') {
          if (message.data) {
            onMessage(message.data);
          }
        }
      } catch (error) {
        console.error('Failed to parse project creation progress message:', error);
      }
    };

    ws.onclose = () => {
      console.log(`Project creation progress stream disconnected: ${progressId}`);
      this.progressWebSocket = null;
      
      if (autoReconnect && !this.isReconnecting) {
        this.isReconnecting = true;
        this.reconnectTimeout = setTimeout(() => {
          this.isReconnecting = false;
          this.streamProgress(progressId, onMessage, options);
        }, reconnectDelay);
      }
    };

    ws.onerror = (error) => {
      console.error('Project creation progress WebSocket error:', error);
    };

    return ws;
  }

  /**
   * Disconnect from progress stream
   */
  disconnect(): void {
    if (this.progressWebSocket) {
      this.progressWebSocket.close();
      this.progressWebSocket = null;
    }
    
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    
    this.isReconnecting = false;
  }

  /**
   * Check if currently connected to a progress stream
   */
  isConnected(): boolean {
    return this.progressWebSocket !== null && this.progressWebSocket.readyState === WebSocket.OPEN;
  }

  // Backward compatibility methods - now just wrappers around streamProgress
  connect(progressId: string): void {
    // This method is kept for backward compatibility but does nothing
    // Use streamProgress instead
    console.warn('projectCreationProgressService.connect() is deprecated. Use streamProgress() instead.');
  }

  onProgress(callback: ProgressCallback): void {
    console.warn('projectCreationProgressService.onProgress() is deprecated. Pass callback to streamProgress() instead.');
  }

  onCompleted(callback: ProgressCallback): void {
    console.warn('projectCreationProgressService.onCompleted() is deprecated. Pass callback to streamProgress() instead.');
  }

  onError(callback: (error: Error) => void): void {
    console.warn('projectCreationProgressService.onError() is deprecated. Pass callback to streamProgress() instead.');
  }
}

// Export singleton instance
export const projectCreationProgressService = new ProjectCreationProgressService(); 