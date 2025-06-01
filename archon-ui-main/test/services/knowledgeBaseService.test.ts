import { describe, it, expect, beforeEach, vi } from 'vitest';
import { knowledgeBaseService } from '@/services/knowledgeBaseService';

// Mock fetch globally
global.fetch = vi.fn();

describe('KnowledgeBaseService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getKnowledgeItems', () => {
    it('should fetch knowledge items with default parameters', async () => {
      const mockResponse = {
        items: [
          {
            id: '1',
            title: 'React Documentation',
            url: 'https://react.dev',
            source_id: 'react-docs',
            metadata: {
              knowledge_type: 'technical',
              tags: ['react', 'frontend'],
              source_type: 'url',
              status: 'active',
              last_scraped: '2024-01-20',
              chunks_count: 150,
              word_count: 50000
            },
            created_at: '2024-01-20T10:00:00Z',
            updated_at: '2024-01-20T10:00:00Z'
          }
        ],
        total: 1,
        page: 1,
        per_page: 20
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await knowledgeBaseService.getKnowledgeItems();
      
      expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/knowledge-items?page=1&per_page=20', {
        headers: { 'Content-Type': 'application/json' }
      });
      expect(result).toEqual(mockResponse);
    });

    it('should fetch knowledge items with filters', async () => {
      const mockResponse = { items: [], total: 0, page: 1, per_page: 20 };
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      await knowledgeBaseService.getKnowledgeItems({
        knowledge_type: 'technical',
        tags: ['react', 'frontend'],
        source_type: 'url',
        search: 'hooks',
        page: 2,
        per_page: 10
      });
      
      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8080/api/knowledge-items?page=2&per_page=10&knowledge_type=technical&tags=react%2Cfrontend&source_type=url&search=hooks',
        {
          headers: { 'Content-Type': 'application/json' }
        }
      );
    });

    it('should handle errors when fetching knowledge items', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ error: 'Internal server error' })
      });

      await expect(knowledgeBaseService.getKnowledgeItems()).rejects.toThrow('Internal server error');
    });
  });

  describe('deleteKnowledgeItem', () => {
    it('should delete a knowledge item by source_id', async () => {
      const mockResponse = { success: true, message: 'Knowledge item deleted' };
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await knowledgeBaseService.deleteKnowledgeItem('react-docs');
      
      expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/knowledge-items/react-docs', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' }
      });
      expect(result).toEqual(mockResponse);
    });

    it('should handle errors when deleting knowledge item', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({ error: 'Knowledge item not found' })
      });

      await expect(knowledgeBaseService.deleteKnowledgeItem('non-existent')).rejects.toThrow('Knowledge item not found');
    });
  });

  describe('updateKnowledgeItem', () => {
    it('should update knowledge item metadata', async () => {
      const updates = {
        knowledge_type: 'business',
        tags: ['project', 'management'],
        update_frequency: 30
      };
      
      const mockResponse = { 
        success: true, 
        message: 'Knowledge item updated',
        source_id: 'react-docs'
      };
      
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await knowledgeBaseService.updateKnowledgeItem('react-docs', updates);
      
      expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/knowledge-items/react-docs', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
      expect(result).toEqual(mockResponse);
    });

    it('should handle errors when updating knowledge item', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: 'Invalid update data' })
      });

      await expect(
        knowledgeBaseService.updateKnowledgeItem('react-docs', {})
      ).rejects.toThrow('Invalid update data');
    });
  });

  describe('uploadDocument', () => {
    it('should upload a document with metadata', async () => {
      const mockFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
      const metadata = {
        knowledge_type: 'technical',
        tags: ['architecture', 'system-design']
      };
      
      const mockResponse = {
        success: true,
        source_id: 'test-pdf-123',
        filename: 'test.pdf',
        chunks_created: 10,
        message: 'Document uploaded successfully'
      };
      
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await knowledgeBaseService.uploadDocument(mockFile, metadata);
      
      // Verify FormData was used
      expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/documents/upload', {
        method: 'POST',
        body: expect.any(FormData)
      });
      
      // Get the FormData that was sent
      const callArgs = (fetch as any).mock.calls[0];
      const formData = callArgs[1].body;
      expect(formData.get('file')).toBe(mockFile);
      expect(formData.get('metadata')).toBe(JSON.stringify(metadata));
      
      expect(result).toEqual(mockResponse);
    });

    it('should handle upload errors', async () => {
      const mockFile = new File(['test'], 'test.pdf', { type: 'application/pdf' });
      
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 413,
        json: async () => ({ error: 'File too large' })
      });

      await expect(
        knowledgeBaseService.uploadDocument(mockFile, {})
      ).rejects.toThrow('File too large');
    });
  });

  describe('crawlUrl', () => {
    it('should start URL crawling with metadata', async () => {
      const crawlRequest = {
        url: 'https://docs.example.com',
        knowledge_type: 'technical',
        tags: ['api', 'documentation'],
        update_frequency: 7,
        crawl_options: {
          max_depth: 3,
          max_concurrent: 5
        }
      };
      
      const mockResponse = {
        success: true,
        source_id: 'docs-example-com',
        message: 'Crawling started',
        estimated_pages: 50
      };
      
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await knowledgeBaseService.crawlUrl(crawlRequest);
      
      expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/knowledge-items/crawl', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(crawlRequest)
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('getKnowledgeItemDetails', () => {
    it('should fetch detailed information about a knowledge item', async () => {
      const mockResponse = {
        source_id: 'react-docs',
        title: 'React Documentation',
        url: 'https://react.dev',
        metadata: {
          knowledge_type: 'technical',
          tags: ['react', 'frontend'],
          chunks_count: 150,
          word_count: 50000,
          pages_crawled: 25,
          last_scraped: '2024-01-20T10:00:00Z'
        },
        chunks: [
          {
            id: 1,
            chunk_number: 1,
            content: 'React is a JavaScript library...',
            url: 'https://react.dev/learn'
          }
        ],
        created_at: '2024-01-20T10:00:00Z',
        updated_at: '2024-01-20T10:00:00Z'
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await knowledgeBaseService.getKnowledgeItemDetails('react-docs');
      
      expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/knowledge-items/react-docs/details', {
        headers: { 'Content-Type': 'application/json' }
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('searchKnowledgeBase', () => {
    it('should search across knowledge base with query', async () => {
      const mockResponse = {
        results: [
          {
            content: 'React hooks allow you to...',
            score: 0.95,
            source: 'react-docs',
            metadata: {
              title: 'React Documentation',
              url: 'https://react.dev/learn/hooks',
              knowledge_type: 'technical'
            }
          }
        ],
        query: 'how to use react hooks',
        sources_searched: ['react-docs', 'nextjs-docs'],
        total_results: 1
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await knowledgeBaseService.searchKnowledgeBase('how to use react hooks', {
        knowledge_type: 'technical',
        sources: ['react-docs', 'nextjs-docs'],
        limit: 10
      });
      
      expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/knowledge-items/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: 'how to use react hooks',
          knowledge_type: 'technical',
          sources: ['react-docs', 'nextjs-docs'],
          limit: 10
        })
      });
      expect(result).toEqual(mockResponse);
    });
  });
}); 