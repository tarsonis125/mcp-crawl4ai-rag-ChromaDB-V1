/**
 * API service layer for communicating with the MCP server backend.
 */

// Types for API responses
export interface MCPServerResponse {
  success: boolean
  status: 'starting' | 'running' | 'stopped' | 'error'
  message?: string
}

export interface MCPServerStatus {
  status: 'starting' | 'running' | 'stopped' | 'error'
  uptime?: number
  logs: string[]
}

export interface CrawlResponse {
  success: boolean
  url: string
  chunks_stored?: number
  content_length?: number
  crawl_type?: string
  urls_processed?: number
  total_chunks?: number
  error?: string
}

export interface CrawlOptions {
  max_depth?: number
  max_concurrent?: number
  chunk_size?: number
}

export interface RAGQueryResponse {
  results: Array<{
    content: string
    score: number
    source?: string
  }>
  query: string
}

export interface RAGQueryOptions {
  source?: string
  match_count?: number
}

export interface SourcesResponse {
  sources: string[]
}

export interface UploadResponse {
  success: boolean
  filename: string
  chunks_created?: number
  error?: string
}

export interface UploadOptions {
  tags?: string[]
  knowledge_type?: 'technical' | 'business'
}

export interface DatabaseMetrics {
  documents: number
  storage_used: string
  last_sync: string
}

// Base API configuration
const API_BASE_URL = '/api'

/**
 * Generic API request handler with error handling
 */
// Retry wrapper for transient errors
export async function retry<T>(fn: () => Promise<T>, retries = 3, delay = 500): Promise<T> {
  let lastError;
  for (let i = 0; i < retries; i++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      if (i < retries - 1) {
        await new Promise(res => setTimeout(res, delay * Math.pow(2, i)));
      }
    }
  }
  throw lastError;
}

async function apiRequest<T>(
// Retry wrapper for transient errors
async function retry<T>(fn: () => Promise<T>, retries = 3, delay = 500): Promise<T> {
  let lastError;
  for (let i = 0; i < retries; i++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      if (i < retries - 1) {
        await new Promise(res => setTimeout(res, delay * Math.pow(2, i)));
      }
    }
  }
  throw lastError;
}

  endpoint: string, 
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    })

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}`
      try {
        const errorData = await response.json()
        errorMessage = errorData.error || errorMessage
      } catch {
        // If JSON parsing fails, use the status text
        errorMessage = response.statusText || errorMessage
      }
      throw new Error(errorMessage)
    }

    return await response.json()
  } catch (error) {
    if (error instanceof Error) {
      throw error
    }
    throw new Error('Unknown error occurred')
  }
}

// MCP Server Management
export async function startMCPServer(): Promise<MCPServerResponse> {
  try {
    return await apiRequest<MCPServerResponse>('/mcp/start', {
      method: 'POST',
    })
  } catch (error) {
    throw new Error(`Failed to start MCP server: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

export async function stopMCPServer(): Promise<MCPServerResponse> {
  try {
    return await apiRequest<MCPServerResponse>('/mcp/stop', {
      method: 'POST',
    })
  } catch (error) {
    throw new Error(`Failed to stop MCP server: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

export async function getMCPServerStatus(): Promise<MCPServerStatus> {
  try {
    return await apiRequest<MCPServerStatus>('/mcp/status')
  } catch (error) {
    throw new Error(`Failed to get server status: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

// Crawling Operations
export async function crawlSinglePage(url: string): Promise<CrawlResponse> {
  try {
    return await apiRequest<CrawlResponse>('/crawl/single', {
      method: 'POST',
      body: JSON.stringify({ url }),
    })
  } catch (error) {
    throw new Error(`Failed to crawl page: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

export async function smartCrawlUrl(url: string, options: CrawlOptions = {}): Promise<CrawlResponse> {
  try {
    return await apiRequest<CrawlResponse>('/crawl/smart', {
      method: 'POST',
      body: JSON.stringify({ url, ...options }),
    })
  } catch (error) {
    throw new Error(`Failed to smart crawl URL: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

// RAG Operations
export async function performRAGQuery(query: string, options: RAGQueryOptions = {}): Promise<RAGQueryResponse> {
  try {
    return await apiRequest<RAGQueryResponse>('/rag/query', {
      method: 'POST',
      body: JSON.stringify({ query, ...options }),
    })
  } catch (error) {
    throw new Error(`Failed to perform RAG query: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

export async function getAvailableSources(): Promise<SourcesResponse> {
  try {
    return await apiRequest<SourcesResponse>('/rag/sources')
  } catch (error) {
    throw new Error(`Failed to get available sources: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

// Document Upload
export async function uploadDocument(file: File, options: UploadOptions = {}): Promise<UploadResponse> {
  try {
    const formData = new FormData()
    formData.append('file', file)
    
    if (options.tags) {
      formData.append('tags', JSON.stringify(options.tags))
    }
    
    if (options.knowledge_type) {
      formData.append('knowledge_type', options.knowledge_type)
    }

    return await apiRequest<UploadResponse>('/documents/upload', {
      method: 'POST',
      body: formData,
      headers: {}, // Don't set Content-Type for FormData, let browser set it
    })
  } catch (error) {
    throw new Error(`Failed to upload document: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

// Database Metrics
export async function getDatabaseMetrics(): Promise<DatabaseMetrics> {
  try {
    return await apiRequest<DatabaseMetrics>('/database/metrics')
  } catch (error) {
    throw new Error(`Failed to get database metrics: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}