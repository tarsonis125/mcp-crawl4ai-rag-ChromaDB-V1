import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mcpService } from '@/services/mcpService';

// Mock fetch globally
global.fetch = vi.fn();

describe('MCPService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Server Management', () => {
    it('should start the MCP server', async () => {
      const mockResponse = { success: true, status: 'starting', message: 'MCP server is starting' };
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await mcpService.startServer();
      
      expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/mcp/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      expect(result).toEqual(mockResponse);
    });

    it('should stop the MCP server', async () => {
      const mockResponse = { success: true, status: 'stopped', message: 'MCP server stopped' };
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await mcpService.stopServer();
      
      expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/mcp/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      expect(result).toEqual(mockResponse);
    });

    it('should get server status', async () => {
      const mockStatus = { status: 'running', uptime: 3600, logs: ['Server started'] };
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockStatus
      });

      const result = await mcpService.getStatus();
      
      expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/mcp/status');
      expect(result).toEqual(mockStatus);
    });

    it('should handle server start errors', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ error: 'Server start failed' })
      });

      await expect(mcpService.startServer()).rejects.toThrow('Failed to start MCP server');
    });
  });

  describe('Log Streaming', () => {
    it('should establish WebSocket connection for log streaming', () => {
      const mockCallback = vi.fn();
      const ws = mcpService.streamLogs(mockCallback);
      
      expect(ws).toBeDefined();
      expect(ws.url).toBe('ws://localhost:8080/api/mcp/logs');
    });

    it('should handle incoming log messages', () => {
      const mockCallback = vi.fn();
      const ws = mcpService.streamLogs(mockCallback);
      
      // Simulate incoming message
      const logData = { 
        timestamp: '2024-01-20T10:00:00Z', 
        level: 'INFO', 
        message: 'Server started' 
      };
      
      // Trigger the onmessage handler
      if (ws.onmessage) {
        ws.onmessage({ data: JSON.stringify(logData) } as MessageEvent);
      }
      
      expect(mockCallback).toHaveBeenCalledWith(logData);
    });

    it('should reconnect on WebSocket disconnection', () => {
      const mockCallback = vi.fn();
      const ws = mcpService.streamLogs(mockCallback, { autoReconnect: true });
      
      // Simulate disconnection
      if (ws.onclose) {
        ws.onclose({} as CloseEvent);
      }
      
      // Should attempt to reconnect
      expect(mcpService.isReconnecting).toBe(true);
    });

    it('should clean up WebSocket on disconnect', () => {
      const mockCallback = vi.fn();
      const ws = mcpService.streamLogs(mockCallback);
      
      mcpService.disconnectLogs();
      
      expect(ws.close).toHaveBeenCalled();
    });
  });

  describe('Configuration', () => {
    it('should get server configuration', async () => {
      const mockConfig = {
        transport: 'sse',
        host: 'localhost',
        port: 8051,
        model: 'gpt-4o-mini'
      };
      
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockConfig
      });

      const result = await mcpService.getConfiguration();
      
      expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/mcp/config');
      expect(result).toEqual(mockConfig);
    });

    it('should save server configuration', async () => {
      const newConfig = { transport: 'stdio' };
      const mockResponse = { success: true, message: 'Configuration updated' };
      
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await mcpService.updateConfiguration(newConfig);
      
      expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/mcp/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig)
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('Server Logs Management', () => {
    it('should fetch historical logs', async () => {
      const mockLogs = [
        { timestamp: '2024-01-20T10:00:00Z', level: 'INFO', message: 'Server started' },
        { timestamp: '2024-01-20T10:00:01Z', level: 'INFO', message: 'Ready to accept connections' }
      ];
      
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockLogs
      });

      const result = await mcpService.getLogs({ limit: 100 });
      
      expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/mcp/logs?limit=100');
      expect(result).toEqual(mockLogs);
    });

    it('should clear server logs', async () => {
      const mockResponse = { success: true, message: 'Logs cleared' };
      
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await mcpService.clearLogs();
      
      expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/mcp/logs', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' }
      });
      expect(result).toEqual(mockResponse);
    });
  });
}); 