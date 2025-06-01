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

type ProgressEventType = 'progress' | 'completed' | 'error';
type ProgressCallback = (data: CrawlProgressData) => void;
type ErrorCallback = (error: Error) => void;

class CrawlProgressService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectInterval = 1000;
  private progressId: string | null = null;
  
  // Event listeners
  private progressCallbacks: ProgressCallback[] = [];
  private errorCallbacks: ErrorCallback[] = [];
  private completedCallbacks: ProgressCallback[] = [];

  /**
   * Connect to the crawl progress WebSocket stream
   */
  connect(progressId: string): void {
    this.progressId = progressId;
    const wsUrl = `ws://localhost:8080/api/crawl-progress/${progressId}`;
    
    if (this.ws) {
      this.disconnect();
    }

    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      console.log(`Connected to crawl progress stream: ${progressId}`);
      this.reconnectAttempts = 0;
    };
    
    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this.handleMessage(message);
      } catch (error) {
        console.error('Failed to parse progress message:', error);
      }
    };
    
    this.ws.onclose = () => {
      console.log(`Crawl progress stream disconnected: ${progressId}`);
      this.attemptReconnect();
    };
    
    this.ws.onerror = (error) => {
      console.error('Crawl progress WebSocket error:', error);
      this.errorCallbacks.forEach(callback => {
        try {
          callback(new Error('WebSocket connection failed'));
        } catch (err) {
          console.error('Error in progress error callback:', err);
        }
      });
    };
  }

  /**
   * Handle incoming WebSocket messages
   */
  private handleMessage(message: any): void {
    const { type, data } = message;
    
    switch (type) {
      case 'crawl_progress':
        this.progressCallbacks.forEach(callback => {
          try {
            callback(data);
          } catch (error) {
            console.error('Error in progress callback:', error);
          }
        });
        break;
        
      case 'crawl_completed':
        this.completedCallbacks.forEach(callback => {
          try {
            callback(data);
          } catch (error) {
            console.error('Error in completed callback:', error);
          }
        });
        // Also notify progress callbacks for UI updates
        this.progressCallbacks.forEach(callback => {
          try {
            callback({ ...data, status: 'completed' });
          } catch (error) {
            console.error('Error in progress callback:', error);
          }
        });
        break;
        
      case 'crawl_error':
        this.errorCallbacks.forEach(callback => {
          try {
            callback(new Error(data.error || 'Crawling failed'));
          } catch (error) {
            console.error('Error in error callback:', error);
          }
        });
        // Also notify progress callbacks for UI updates
        this.progressCallbacks.forEach(callback => {
          try {
            callback({ ...data, status: 'error' });
          } catch (error) {
            console.error('Error in progress callback:', error);
          }
        });
        break;
        
      case 'heartbeat':
        // Ignore heartbeat messages
        break;
        
      default:
        console.warn('Unknown progress message type:', type);
    }
  }

  /**
   * Attempt to reconnect to the WebSocket
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts && this.progressId) {
      setTimeout(() => {
        console.log(`Attempting to reconnect... (${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);
        this.reconnectAttempts++;
        this.connect(this.progressId!);
      }, this.reconnectInterval * Math.pow(2, this.reconnectAttempts));
    }
  }

  /**
   * Register a callback for progress updates
   */
  onProgress(callback: ProgressCallback): void {
    this.progressCallbacks.push(callback);
  }

  /**
   * Register a callback for completion events
   */
  onCompleted(callback: ProgressCallback): void {
    this.completedCallbacks.push(callback);
  }

  /**
   * Register a callback for error events
   */
  onError(callback: ErrorCallback): void {
    this.errorCallbacks.push(callback);
  }

  /**
   * Remove a progress callback
   */
  removeProgressCallback(callback: ProgressCallback): void {
    const index = this.progressCallbacks.indexOf(callback);
    if (index > -1) {
      this.progressCallbacks.splice(index, 1);
    }
  }

  /**
   * Remove an error callback
   */
  removeErrorCallback(callback: ErrorCallback): void {
    const index = this.errorCallbacks.indexOf(callback);
    if (index > -1) {
      this.errorCallbacks.splice(index, 1);
    }
  }

  /**
   * Emit an event (for testing purposes)
   */
  emit(eventType: ProgressEventType, data: any): void {
    const message = { type: eventType, data };
    this.handleMessage(message);
  }

  /**
   * Reconnect to the current progress stream
   */
  reconnect(): void {
    if (this.progressId) {
      this.connect(this.progressId);
    }
  }

  /**
   * Disconnect from the WebSocket and clean up
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.progressId = null;
    this.reconnectAttempts = 0;
    this.progressCallbacks = [];
    this.errorCallbacks = [];
    this.completedCallbacks = [];
  }
}

// Export singleton instance
export const crawlProgressService = new CrawlProgressService(); 