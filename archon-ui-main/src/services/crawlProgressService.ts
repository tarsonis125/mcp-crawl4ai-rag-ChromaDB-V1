export interface ProgressStep {
  id: string;
  label: string;
  percentage: number;
  status: 'pending' | 'active' | 'completed' | 'error';
  message?: string;
}

export interface CrawlProgressData {
  progressId: string;
  status: 'starting' | 'crawling' | 'analyzing' | 'sitemap' | 'text_file' | 'webpage' | 'processing' | 'storing' | 'completed' | 'error' | 'waiting';
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
  // New fields for multi-progress tracking
  steps?: ProgressStep[];
  currentStep?: string;
  stepMessage?: string;
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

    const wsUrl = `${this.wsUrl}/api/crawl-progress/${progressId}`;
    console.log(`🔌 Attempting to connect to WebSocket: ${wsUrl}`);
    console.log(`   Base URL: ${this.baseUrl}`);
    console.log(`   WS URL: ${this.wsUrl}`);
    
    const ws = new WebSocket(wsUrl);
    this.progressWebSocket = ws;

    // Track last received message time for debugging
    let lastMessageTime = Date.now();
    let heartbeatTimeout: NodeJS.Timeout | null = null;

    ws.onopen = () => {
      console.log(`🚀 Connected to crawl progress stream: ${progressId}`);
      this.isReconnecting = false;
      lastMessageTime = Date.now();
      
      // Set up heartbeat timeout detection
      heartbeatTimeout = setTimeout(() => {
        const timeSinceLastMessage = Date.now() - lastMessageTime;
        console.warn(`⚠️  No messages received for ${timeSinceLastMessage}ms, connection may be stuck`);
        if (timeSinceLastMessage > 60000) { // 60 seconds
          console.error(`❌ Connection appears stuck, forcing reconnection`);
          ws.close(1006, 'Connection timeout');
        }
      }, 65000); // Check after 65 seconds
    };

    ws.onmessage = (event) => {
      try {
        lastMessageTime = Date.now();
        const message = JSON.parse(event.data);
        console.log(`📨 Received WebSocket message:`, message);
        
        // Ignore ping/heartbeat messages
        if (message.type === 'ping' || message.type === 'pong' || message.type === 'heartbeat') {
          return;
        }

        // Handle progress messages
        if (message.type === 'crawl_progress' || message.type === 'crawl_completed' || message.type === 'crawl_error') {
          if (message.data) {
            // Validate the message data
            if (!message.data.progressId) {
              console.warn('⚠️  Received progress message without progressId:', message);
              return;
            }
            
            // Ensure percentage is a valid number
            if (typeof message.data.percentage !== 'number' || isNaN(message.data.percentage)) {
              console.warn('⚠️  Invalid percentage in progress message:', message.data.percentage);
              message.data.percentage = 0;
            }
            
            onMessage(message.data);
          } else {
            console.warn('⚠️  Received progress message without data:', message);
          }
        }
      } catch (error) {
        console.error('❌ Failed to parse progress message:', error);
        console.error('   Raw message:', event.data);
      }
    };

    ws.onclose = (event) => {
      console.log(`❌ Crawl progress stream disconnected: ${progressId}`, event);
      console.log(`   Close code: ${event.code}, reason: ${event.reason}`);
      this.progressWebSocket = null;
      
      // Clear heartbeat timeout
      if (heartbeatTimeout) {
        clearTimeout(heartbeatTimeout);
        heartbeatTimeout = null;
      }
      
      // Only auto-reconnect for unexpected closures (not normal closure or timeout)
      if (autoReconnect && !this.isReconnecting && event.code !== 1000 && event.code !== 1006) {
        this.isReconnecting = true;
        console.log(`🔄 Attempting to reconnect in ${reconnectDelay}ms...`);
        this.reconnectTimeout = setTimeout(() => {
          this.isReconnecting = false;
          this.streamProgress(progressId, onMessage, options);
        }, reconnectDelay);
      }
    };

    ws.onerror = (error) => {
      console.error('❌ Crawl progress WebSocket error:', error);
      console.error('   WebSocket readyState:', ws.readyState);
      console.error('   WebSocket URL:', wsUrl);
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