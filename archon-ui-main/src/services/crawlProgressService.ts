/**
 * Crawl Progress Service
 * 
 * Uses Socket.IO for better reliability, automatic reconnection,
 * and improved connection management.
 */

import { createWebSocketService, WebSocketService } from './socketIOService';

// Define types for crawl progress
export interface WorkerProgress {
  worker_id: string;
  status: string;
  progress: number;
  current_url?: string;
  pages_crawled: number;
  total_pages: number;
  message?: string;
  batch_num?: number;
}

// Simplified batch progress interface
export interface BatchProgress {
  completedBatches: number;
  totalBatches: number;
  currentBatch: number;
  activeWorkers: number;
  chunksInBatch: number;
  totalChunksInBatch: number;
}

export interface CrawlProgressData {
  progressId: string;
  status: string;
  percentage: number;
  currentStep?: string;
  logs?: string[];
  log?: string;
  workers?: WorkerProgress[];  // Deprecated - kept for backward compatibility
  error?: string;
  completed?: boolean;
  // Additional properties for document upload and crawling
  uploadType?: 'document' | 'crawl';
  fileName?: string;
  fileType?: string;
  currentUrl?: string;
  chunksStored?: number;
  processedPages?: number;
  totalPages?: number;
  wordCount?: number;
  duration?: string;
  sourceId?: string;
  // Simplified batch progress (snake_case from backend)
  completed_batches?: number;
  total_batches?: number;
  current_batch?: number;
  active_workers?: number;
  chunks_in_batch?: number;
  total_chunks_in_batch?: number;
  // Legacy fields
  totalJobs?: number;
  parallelWorkers?: number;
  // Camel case aliases for convenience
  completedBatches?: number;
  totalBatches?: number;
  currentBatch?: number;
  activeWorkers?: number;
  chunksInBatch?: number;
  totalChunksInBatch?: number;
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
    // Starting Socket.IO progress stream

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
      this.wsService.addMessageHandler('crawl_progress', (message) => {
        const data = message.data || message;
        // Crawl progress update received
        onMessage(data);
      });

      // Also listen for legacy event names for backward compatibility
      this.wsService.addMessageHandler('progress_update', (message) => {
        const data = message.data || message;
        // Progress update (legacy) received
        onMessage(data);
      });

      this.wsService.addMessageHandler('crawl_complete', (message) => {
        const data = message.data || message;
        // Crawl completed
        onMessage({ ...data, completed: true });
      });

      this.wsService.addMessageHandler('crawl_error', (message) => {
        // Crawl error
        onMessage({ 
          progressId,
          status: 'error',
          error: message.data?.message || message.error || 'Unknown error',
          percentage: 0
        });
      });

      // Subscribe to the crawl progress
      this.wsService.send({
        type: 'crawl_subscribe',
        data: { progress_id: progressId }
      });

      // Store cleanup function
      this.activeSubscriptions.set(progressId, () => {
        this.stopStreaming(progressId);
      });

    } catch (error) {
      // Failed to start progress stream
      throw error;
    }
  }

  /**
   * Stop streaming progress for a specific ID
   */
  stopStreaming(progressId: string): void {
    // Stopping progress stream
    
    if (this.wsService) {
      // Send unsubscribe message
      this.wsService.send({
        type: 'crawl_unsubscribe',
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
    // Stopping all progress streams
    
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