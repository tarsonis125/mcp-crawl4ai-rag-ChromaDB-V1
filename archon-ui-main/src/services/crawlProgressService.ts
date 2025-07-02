/**
 * Crawl Progress Service
 * 
 * Uses Socket.IO for better reliability, automatic reconnection,
 * and improved connection management.
 */

import { knowledgeSocketIO, WebSocketService } from './socketIOService';

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
  private wsService: WebSocketService = knowledgeSocketIO;
  private activeSubscriptions: Map<string, () => void> = new Map();
  private messageHandlers: Map<string, ProgressCallback> = new Map();
  private isConnected: boolean = false;

  /**
   * Stream crawl progress with Socket.IO
   */
  async streamProgress(
    progressId: string,
    onMessage: ProgressCallback,
    options: StreamProgressOptions = {}
  ): Promise<void> {
    console.log(`🚀 Starting Socket.IO progress stream for ${progressId}`);

    try {
      // Ensure we're connected to Socket.IO
      if (!this.isConnected) {
        console.log('📡 Connecting to Socket.IO server...');
        // Connect to the base Socket.IO endpoint (not a specific path)
        await this.wsService.connect('/socket.io');
        this.isConnected = true;
        console.log('✅ Connected to Socket.IO server');
      }

      // Wait for connection to be fully established
      await this.wsService.waitForConnection(5000);
      console.log('✅ Socket.IO connection verified');

      // Create a specific handler for this progressId
      const progressHandler = (message: any) => {
        console.log(`📨 Raw message received:`, message);
        const data = message.data || message;
        console.log(`📨 Extracted data:`, data);
        console.log(`📨 Data progressId: ${data.progressId}, Expected: ${progressId}`);
        
        // Only process messages for this specific progressId
        if (data.progressId === progressId) {
          console.log(`✅ Progress match! Processing message for ${progressId}`);
          onMessage(data);
        } else {
          console.log(`❌ Progress ID mismatch: got ${data.progressId}, expected ${progressId}`);
        }
      };

      // Store the handler so we can remove it later
      this.messageHandlers.set(progressId, progressHandler);

      // Add message handlers
      this.wsService.addMessageHandler('crawl_progress', progressHandler);

      // Also listen for legacy event names for backward compatibility
      this.wsService.addMessageHandler('progress_update', progressHandler);

      this.wsService.addMessageHandler('crawl_complete', (message) => {
        const data = message.data || message;
        console.log(`✅ Crawl completed for ${progressId}`);
        if (data.progressId === progressId) {
          onMessage({ ...data, completed: true });
        }
      });

      this.wsService.addMessageHandler('crawl_error', (message) => {
        console.error(`❌ Crawl error for ${progressId}:`, message);
        if (message.data?.progressId === progressId || message.progressId === progressId) {
          onMessage({ 
            progressId,
            status: 'error',
            error: message.data?.message || message.error || 'Unknown error',
            percentage: 0
          });
        }
      });

      // Listen for subscription acknowledgment
      this.wsService.addMessageHandler('crawl_subscribe_ack', (message) => {
        const data = message.data || message;
        console.log(`✅ Subscription acknowledged for ${data.progress_id}`);
      });

      // Subscribe to the crawl progress
      console.log(`📤 Sending crawl_subscribe for ${progressId}`);
      const subscribeMessage = {
        type: 'crawl_subscribe',
        data: { progress_id: progressId }
      };
      console.log('📤 Subscribe message:', JSON.stringify(subscribeMessage));
      const sent = this.wsService.send(subscribeMessage);
      console.log(`📤 Message sent successfully: ${sent}`);

      // Store cleanup function
      this.activeSubscriptions.set(progressId, () => {
        this.stopStreaming(progressId);
      });

    } catch (error) {
      console.error(`❌ Failed to start progress stream for ${progressId}:`, error);
      throw error;
    }
  }

  /**
   * Stop streaming progress for a specific ID
   */
  stopStreaming(progressId: string): void {
    console.log(`🛑 Stopping progress stream for ${progressId}`);
    
    // Send unsubscribe message
    if (this.isConnected) {
      this.wsService.send({
        type: 'crawl_unsubscribe',
        data: { progress_id: progressId }
      });
    }
    
    // Remove the specific handler for this progressId
    const handler = this.messageHandlers.get(progressId);
    if (handler) {
      this.wsService.removeMessageHandler('crawl_progress', handler);
      this.wsService.removeMessageHandler('progress_update', handler);
      this.messageHandlers.delete(progressId);
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
    
    // Clear all handlers
    this.messageHandlers.clear();
    
    // Note: We don't disconnect the shared Socket.IO connection
    // as it may be used by other services
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
  getConnectionState(): boolean {
    return this.isConnected && this.wsService.isConnected();
  }

  /**
   * Manually trigger reconnection
   */
  async reconnect(): Promise<void> {
    console.log('🔄 Reconnecting to Socket.IO server...');
    this.isConnected = false;
    // The next streamProgress call will reconnect
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
    console.log('🔌 Disconnecting crawl progress service');
    this.stopAllStreams();
    this.isConnected = false;
    // Note: We don't disconnect the shared Socket.IO connection
    // as it may be used by other services
    this.activeSubscriptions.clear();
  }
}

// Export singleton instance
export const crawlProgressService = new CrawlProgressService();