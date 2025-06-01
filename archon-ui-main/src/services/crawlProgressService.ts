export interface CrawlProgressData {
  progressId: string;
  status: 'starting' | 'crawling' | 'completed' | 'error';
  percentage: number;
  currentUrl?: string;
  eta?: string;
  totalPages?: number;
  processedPages?: number;
  chunksStored?: number;
  wordCount?: number;
  duration?: string;
  error?: string;
  logs: string[];
}

interface StreamProgressOptions {
  autoReconnect?: boolean;
  reconnectDelay?: number;
}

type ProgressCallback = (data: CrawlProgressData) => void;

class CrawlProgressService {
  private baseUrl = (import.meta as any).env?.VITE_API_URL || this.getApiBaseUrl();

  private getApiBaseUrl() {
    const protocol = window.location.protocol;
    const host = window.location.hostname;
    const port = '8080'; // Backend API port
    return `${protocol}//${host}:${port}`;
  }

  private wsUrl = this.baseUrl.replace('http', 'ws');
  private progressWebSocket: WebSocket | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  public isReconnecting = false;

  /**
   * Stream crawl progress similar to how MCP logs work
   */
  streamProgress(
    progressId: string,
    onMessage: ProgressCallback,
    options: StreamProgressOptions = {}
  ): WebSocket {
    const { autoReconnect = true, reconnectDelay = 5000 } = options;

    // Close existing connection if any
    this.disconnect();

    const ws = new WebSocket(`${this.wsUrl}/api/crawl-progress/${progressId}`);
    this.progressWebSocket = ws;

    ws.onopen = () => {
      console.log(`🚀 Connected to crawl progress stream: ${progressId}`);
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
        if (message.type === 'crawl_progress' || message.type === 'crawl_completed' || message.type === 'crawl_error') {
          if (message.data) {
            onMessage(message.data);
          }
        }
      } catch (error) {
        console.error('Failed to parse progress message:', error);
      }
    };

    ws.onclose = () => {
      console.log(`Crawl progress stream disconnected: ${progressId}`);
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
      console.error('Crawl progress WebSocket error:', error);
    };

    return ws;
  }

  /**
   * Disconnect from the WebSocket and clean up (similar to MCP service)
   */
  disconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    
    this.isReconnecting = false;

    if (this.progressWebSocket) {
      this.progressWebSocket.close();
      this.progressWebSocket = null;
    }
  }

  // Backward compatibility methods - now just wrappers around streamProgress
  connect(progressId: string): void {
    // This method is kept for backward compatibility but does nothing
    // Use streamProgress instead
    console.warn('crawlProgressService.connect() is deprecated. Use streamProgress() instead.');
  }

  onProgress(callback: ProgressCallback): void {
    console.warn('crawlProgressService.onProgress() is deprecated. Pass callback to streamProgress() instead.');
  }

  onCompleted(callback: ProgressCallback): void {
    console.warn('crawlProgressService.onCompleted() is deprecated. Pass callback to streamProgress() instead.');
  }

  onError(callback: (error: Error) => void): void {
    console.warn('crawlProgressService.onError() is deprecated. Pass callback to streamProgress() instead.');
  }

  removeProgressCallback(callback: ProgressCallback): void {
    // No-op for backward compatibility
  }

  removeErrorCallback(callback: (error: Error) => void): void {
    // No-op for backward compatibility
  }
}

// Export singleton instance
export const crawlProgressService = new CrawlProgressService(); 