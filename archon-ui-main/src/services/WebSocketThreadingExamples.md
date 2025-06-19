# WebSocket-Safe Threading Patterns

This document shows how to use the new WebSocket-safe threading utilities to handle parallel processing without blocking WebSocket connections.

## Quick Start

```typescript
import { knowledgeWebSocket, WebSocketThreadingUtils } from './websocketService';

// Connect to WebSocket first
await knowledgeWebSocket.connect('/api/knowledge/ws');
```

## Pattern 1: Parallel Processing with Progress Updates

**Use Case**: Crawling multiple URLs, processing documents, generating embeddings

```typescript
// ✅ CORRECT: WebSocket-safe parallel processing
const urls = ['url1', 'url2', 'url3', ...];

const results = await knowledgeWebSocket.processParallel(
  urls,
  async (url) => {
    // This runs in parallel but won't block WebSocket
    const response = await fetch(url);
    const data = await response.json();
    return processData(data);
  },
  {
    maxConcurrency: 3,        // Max 3 concurrent requests
    batchSize: 10,           // Process in batches of 10
    progressUpdates: true,   // Send progress via WebSocket
    taskName: 'url_crawling' // Name for progress tracking
  }
);
```

**Frontend receives these WebSocket messages:**
```json
{"type": "processing_progress", "task_name": "url_crawling", "completed": 5, "total": 50, "progress_percent": 10}
{"type": "batch_complete", "completed": 10, "total": 50, "batch_size": 10}
```

## Pattern 2: CPU-Intensive Tasks

**Use Case**: AI processing, large data transformations, complex calculations

```typescript
// ✅ CORRECT: CPU-intensive work that yields control
const result = await knowledgeWebSocket.runCpuIntensiveTask(
  async () => {
    // Heavy processing here
    return await generateEmbeddings(largeDataset);
  },
  {
    taskName: 'embedding_generation',
    progressUpdates: true
  }
);
```

## Pattern 3: Rate-Limited Processing

**Use Case**: API calls with rate limits, avoiding 429 errors

```typescript
// ✅ CORRECT: Respects rate limits while maintaining parallelism
const apiCalls = ['call1', 'call2', 'call3', ...];

const results = await WebSocketThreadingUtils.processWithRateLimit(
  apiCalls,
  async (apiCall) => {
    return await makeAPICall(apiCall);
  },
  {
    rateLimit: 200,          // 200ms between requests
    maxConcurrency: 2,       // Max 2 concurrent calls
    websocket: knowledgeWebSocket,
    taskName: 'api_crawling'
  }
);
```

## Pattern 4: Background Workers

**Use Case**: Continuous processing, job queues, real-time updates

```typescript
// ✅ CORRECT: Background worker that doesn't block WebSocket
const worker = knowledgeWebSocket.createBackgroundWorker(
  async (workItem) => {
    return await processWorkItem(workItem);
  },
  {
    maxConcurrency: 3,
    workerName: 'document_processor',
    progressUpdates: true
  }
);

// Add work to the queue
const result1 = await worker.addWork(document1);
const result2 = await worker.addWork(document2);

// Check queue size
console.log('Queue size:', worker.getQueueSize());

// Stop worker when done
worker.stop();
```

## ❌ WRONG vs ✅ RIGHT Patterns

### Wrong: Blocking the Event Loop
```typescript
// ❌ BAD: This blocks WebSocket completely
for (const url of urls) {
  await fetch(url);        // Sequential, slow
  await processResponse(); // Blocks event loop
  // WebSocket can't send/receive messages!
}
```

### Right: WebSocket-Safe Processing
```typescript
// ✅ GOOD: This maintains WebSocket health
const results = await knowledgeWebSocket.processParallel(
  urls,
  async (url) => {
    const response = await fetch(url);
    return await processResponse(response);
  },
  { 
    maxConcurrency: 3,
    progressUpdates: true 
  }
);
```

### Wrong: No Rate Limiting
```typescript
// ❌ BAD: Overwhelms servers, causes disconnects
const promises = urls.map(url => fetch(url));
await Promise.all(promises); // Rate limit violations!
```

### Right: Smart Rate Limiting
```typescript
// ✅ GOOD: Respects limits, maintains connection
await WebSocketThreadingUtils.processWithRateLimit(
  urls,
  async (url) => fetch(url),
  { rateLimit: 100, maxConcurrency: 3 }
);
```

## Real-World Example: Knowledge Base Crawling

```typescript
async function crawlKnowledgeBase(urls: string[]) {
  // Connect WebSocket
  await knowledgeWebSocket.connect('/api/knowledge/ws');
  
  try {
    // Step 1: Crawl URLs with rate limiting
    const crawlResults = await knowledgeWebSocket.processParallel(
      urls,
      async (url) => {
        const response = await fetch(`/api/crawl`, {
          method: 'POST',
          body: JSON.stringify({ url }),
          headers: { 'Content-Type': 'application/json' }
        });
        return response.json();
      },
      {
        maxConcurrency: 3,
        batchSize: 5,
        progressUpdates: true,
        taskName: 'knowledge_crawling'
      }
    );
    
    // Step 2: Process documents in background
    const worker = knowledgeWebSocket.createBackgroundWorker(
      async (document) => {
        return await generateEmbeddings(document);
      },
      {
        maxConcurrency: 2,
        workerName: 'embedding_generator',
        progressUpdates: true
      }
    );
    
    // Add documents to worker queue
    const embeddingPromises = crawlResults.map(doc => worker.addWork(doc));
    const embeddings = await Promise.all(embeddingPromises);
    
    // Clean up
    worker.stop();
    
    return { crawlResults, embeddings };
    
  } catch (error) {
    console.error('Crawling failed:', error);
    throw error;
  }
}
```

## Frontend Progress Handling

```typescript
// Listen for progress updates in your React component
useEffect(() => {
  knowledgeWebSocket.addEventListener('message', (message) => {
    const data = JSON.parse(message.data);
    
    switch (data.type) {
      case 'processing_progress':
        setProgress({
          completed: data.completed,
          total: data.total,
          percent: data.progress_percent,
          taskName: data.task_name
        });
        break;
        
      case 'batch_complete':
        console.log(`Batch completed: ${data.completed}/${data.total}`);
        break;
        
      case 'task_completed':
        console.log(`Task finished: ${data.task_name}`);
        setProgress(null);
        break;
        
      case 'worker_item_completed':
        console.log(`Worker processed item: ${data.worker_name}`);
        break;
    }
  });
}, []);
```

## Key Benefits

1. **✅ WebSocket Health**: No more disconnect screens during processing
2. **⚡ Performance**: True parallel processing with smart concurrency control
3. **🛡️ Rate Limiting**: Built-in protection against API rate limits
4. **📊 Progress Tracking**: Real-time updates to the frontend
5. **🔄 Error Recovery**: Graceful handling of failures without breaking connections
6. **🧵 Memory Safety**: Batch processing prevents memory overload

## Migration Guide

### Old Pattern (Breaks WebSockets)
```typescript
// This causes disconnects!
for (const item of items) {
  await processItem(item);
}
```

### New Pattern (WebSocket Safe)
```typescript
// This maintains WebSocket health!
await knowledgeWebSocket.processParallel(items, processItem, {
  maxConcurrency: 3,
  progressUpdates: true
});
```

The key is to **always use the WebSocket-safe utilities** for any processing that takes more than a few milliseconds! 