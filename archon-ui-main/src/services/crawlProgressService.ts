/**
 * Crawl Progress Service
 * 
 * Uses Socket.IO for better reliability, automatic reconnection,
 * and improved connection management.
 */

import { createWebSocketService, WebSocketService } from './webSocketService';

// Define types for crawl progress
export interface WorkerProgress {
  worker_id: string;
  status: string;
  progress: number;
  current_url?: string;
  pages_crawled: number;
  total_pages: number;
  message?: string;
}

export interface CrawlProgressData {
  progressId: string;
  status: string;
  percentage: number;
  currentStep?: string;
  logs?: string[];
  workers?: WorkerProgress[];
  error?: string;
  completed?: boolean;
  // Additional properties for document upload and crawling
  uploadType?: 'document' | 'crawl';
  fileName?: string;
  currentUrl?: string;
  chunksStored?: number;
}

export interface ProgressStep {
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  percentage: number;
}

interface StreamProgressOptions {
  autoReconnect?: boolean;
  reconnectDelay?: number;
  connectionTimeout?: number;
}

type ProgressCallback = (data: any) => void;

class CrawlProgressService {
  private wsService: WebSocketService | null = null;
  private activeSubscriptions: Map<string, () => void> = new Map();

  /**
   * Stream crawl progress with Socket.IO
   */
  async streamProgress(
    progressId: string,
    onMessage: ProgressCallback,
    options: StreamProgressOptions = {}
  ): Promise<void> {
    console.log(`📡 Starting Socket.IO progress stream for ${progressId}`);

    try {
      // Create WebSocket service if not exists
      if (!this.wsService) {
        this.wsService = createWebSocketService({
          enableAutoReconnect: options.autoReconnect ?? true,
          reconnectInterval: options.reconnectDelay ?? 1000
        });
      }

      // Connect to crawl progress endpoint
      const endpoint = `/api/crawl-progress/${progressId}`;
      await this.wsService.connect(endpoint);

      // Add message handlers
      this.wsService.addMessageHandler('progress_update', (message) => {
        onMessage(message.data || message);
      });

      this.wsService.addMessageHandler('progress_complete', (message) => {
        onMessage(message.data || message);
        console.log(`Progress completed for ${progressId}`);
      });

      this.wsService.addMessageHandler('error', (message) => {
        console.error(`Progress error for ${progressId}:`, message);
        onMessage({ error: message.data?.message || 'Unknown error' });
      });

      // Subscribe to the progress
      this.wsService.send({
        type: 'subscribe',
        data: { progress_id: progressId }
      });

      // Store cleanup function
      this.activeSubscriptions.set(progressId, () => {
        this.stopStreaming(progressId);
      });

    } catch (error) {
      console.error(`Failed to start progress stream for ${progressId}:`, error);
      throw error;
    }
  }

  /**
   * Stop streaming progress for a specific ID
   */
  stopStreaming(progressId: string): void {
    console.log(`🛑 Stopping progress stream for ${progressId}`);
    
    if (this.wsService) {
      // Send unsubscribe message
      this.wsService.send({
        type: 'unsubscribe',
        data: { progress_id: progressId }
      });
    }
    
    // Remove from active subscriptions
    this.activeSubscriptions.delete(progressId);
  }

  /**
   * Stop all active streams
   */
  stopAllStreams(): void {
    console.log('🛑 Stopping all progress streams');
    
    // Stop each active subscription
    for (const [progressId] of this.activeSubscriptions) {
      this.stopStreaming(progressId);
    }
    
    // Disconnect WebSocket
    if (this.wsService) {
      this.wsService.disconnect();
      this.wsService = null;
    }
  }

  /**
   * Check if currently streaming for a progress ID
   */
  isStreaming(progressId: string): boolean {
    return this.activeSubscriptions.has(progressId);
  }

  /**
   * Get connection state
   */
  isConnected(): boolean {
    return this.wsService?.isConnected() ?? false;
  }

  /**
   * Manually trigger reconnection
   */
  async reconnect(): Promise<void> {
    if (!this.wsService) {
      this.wsService = createWebSocketService({
        enableAutoReconnect: true
      });
    }
    // Connection happens when streaming starts
  }

  /**
   * Enhanced stream progress with additional callbacks
   */
  async streamProgressEnhanced(
    progressId: string,
    callbacks: {
      onMessage: ProgressCallback;
      onStateChange?: (state: any) => void;
      onError?: (error: any) => void;
    },
    options: StreamProgressOptions = {}
  ): Promise<void> {
    // Use regular streamProgress with error handling
    try {
      await this.streamProgress(progressId, callbacks.onMessage, options);
      
      // Add state change handler if provided
      if (callbacks.onStateChange && this.wsService) {
        this.wsService.addStateChangeHandler(callbacks.onStateChange);
      }
      
      // Add error handler if provided
      if (callbacks.onError && this.wsService) {
        this.wsService.addErrorHandler(callbacks.onError);
      }
    } catch (error) {
      if (callbacks.onError) {
        callbacks.onError(error);
      }
      throw error;
    }
  }

  /**
   * Wait for connection to be established
   */
  async waitForConnection(timeout: number = 5000): Promise<void> {
    if (!this.wsService) {
      throw new Error('WebSocket service not initialized');
    }
    return this.wsService.waitForConnection(timeout);
  }

  /**
   * Disconnect the WebSocket service
   */
  disconnect(): void {
    if (this.wsService) {
      this.wsService.disconnect();
      this.wsService = null;
    }
    this.activeSubscriptions.clear();
  }
}

// Export singleton instance
export const crawlProgressService = new CrawlProgressService();