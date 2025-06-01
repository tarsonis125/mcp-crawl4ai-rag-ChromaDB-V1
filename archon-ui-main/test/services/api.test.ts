/**
 * Tests for API service layer.
 * These tests will initially fail until the API service module is implemented.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { 
  startMCPServer, 
  stopMCPServer, 
  getMCPServerStatus,
  crawlSinglePage,
  smartCrawlUrl,
  performRAGQuery,
  getAvailableSources,
  uploadDocument,
  getDatabaseMetrics
} from '@/services/api'

// Mock fetch globally
const mockFetch = vi.fn()
global.fetch = mockFetch

describe('API Service Layer', () => {
  beforeEach(() => {
    mockFetch.mockClear()
  })

  describe('MCP Server Management', () => {
    it('should start MCP server successfully', async () => {
      // This will fail until we create the api service
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, status: 'starting' })
      })

      const result = await startMCPServer()
      
      expect(mockFetch).toHaveBeenCalledWith('/api/mcp/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      expect(result.success).toBe(true)
      expect(result.status).toBe('starting')
    })

    it('should stop MCP server successfully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true, status: 'stopped' })
      })

      const result = await stopMCPServer()
      
      expect(mockFetch).toHaveBeenCalledWith('/api/mcp/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      expect(result.success).toBe(true)
      expect(result.status).toBe('stopped')
    })

    it('should get MCP server status', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ 
          status: 'running', 
          uptime: 3600,
          logs: ['Server started', 'Ready to accept connections']
        })
      })

      const result = await getMCPServerStatus()
      
      expect(mockFetch).toHaveBeenCalledWith('/api/mcp/status', {
        headers: { 'Content-Type': 'application/json' }
      })
      expect(result.status).toBe('running')
      expect(result.uptime).toBe(3600)
      expect(result.logs).toHaveLength(2)
    })

    it('should handle server management errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ error: 'Internal server error' })
      })

      await expect(startMCPServer()).rejects.toThrow('Failed to start MCP server')
    })
  })

  describe('Crawling Operations', () => {
    it('should crawl single page successfully', async () => {
      const mockResponse = {
        success: true,
        url: 'https://example.com',
        chunks_stored: 5,
        content_length: 1500
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      const result = await crawlSinglePage('https://example.com')
      
      expect(mockFetch).toHaveBeenCalledWith('/api/crawl/single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: 'https://example.com' })
      })
      expect(result.success).toBe(true)
      expect(result.chunks_stored).toBe(5)
    })

    it('should smart crawl URL with options', async () => {
      const mockResponse = {
        success: true,
        crawl_type: 'webpage',
        urls_processed: 10,
        total_chunks: 50
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      const options = { max_depth: 2, max_concurrent: 5 }
      const result = await smartCrawlUrl('https://example.com', options)
      
      expect(mockFetch).toHaveBeenCalledWith('/api/crawl/smart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          url: 'https://example.com',
          ...options
        })
      })
      expect(result.success).toBe(true)
      expect(result.urls_processed).toBe(10)
    })

    it('should handle crawling errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: 'Invalid URL' })
      })

      await expect(crawlSinglePage('invalid-url')).rejects.toThrow('Failed to crawl page')
    })
  })

  describe('RAG Operations', () => {
    it('should perform RAG query successfully', async () => {
      const mockResponse = {
        results: [
          { content: 'Relevant content 1', score: 0.95 },
          { content: 'Relevant content 2', score: 0.87 }
        ],
        query: 'test query'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      const result = await performRAGQuery('test query', { source: 'example.com' })
      
      expect(mockFetch).toHaveBeenCalledWith('/api/rag/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query: 'test query',
          source: 'example.com'
        })
      })
      expect(result.results).toHaveLength(2)
      expect(result.results[0].score).toBe(0.95)
    })

    it('should get available sources', async () => {
      const mockResponse = {
        sources: ['example.com', 'docs.example.com', 'blog.example.com']
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      const result = await getAvailableSources()
      
      expect(mockFetch).toHaveBeenCalledWith('/api/rag/sources', {
        headers: { 'Content-Type': 'application/json' }
      })
      expect(result.sources).toHaveLength(3)
      expect(result.sources).toContain('example.com')
    })
  })

  describe('Document Upload', () => {
    it('should upload document successfully', async () => {
      const mockFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' })
      const mockResponse = {
        success: true,
        filename: 'test.pdf',
        chunks_created: 3
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      const result = await uploadDocument(mockFile, { tags: ['test'] })
      
      expect(mockFetch).toHaveBeenCalledWith('/api/documents/upload', {
        method: 'POST',
        body: expect.any(FormData),
        headers: {}
      })
      expect(result.success).toBe(true)
      expect(result.filename).toBe('test.pdf')
    })

    it('should handle upload errors', async () => {
      const mockFile = new File(['test'], 'test.txt', { type: 'text/plain' })
      
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 413,
        json: async () => ({ error: 'File too large' })
      })

      await expect(uploadDocument(mockFile)).rejects.toThrow('Failed to upload document')
    })
  })

  describe('Database Metrics', () => {
    it('should get database metrics successfully', async () => {
      const mockResponse = {
        documents: 256,
        storage_used: '1.2 GB',
        last_sync: '2024-01-20T10:30:00Z'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      const result = await getDatabaseMetrics()
      
      expect(mockFetch).toHaveBeenCalledWith('/api/database/metrics', {
        headers: { 'Content-Type': 'application/json' }
      })
      expect(result.documents).toBe(256)
      expect(result.storage_used).toBe('1.2 GB')
    })
  })

  describe('Error Handling', () => {
    it('should handle network errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'))

      await expect(getMCPServerStatus()).rejects.toThrow('Network error')
    })

    it('should handle non-JSON responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => { throw new Error('Invalid JSON') }
      })

      await expect(getMCPServerStatus()).rejects.toThrow()
    })
  })
})
