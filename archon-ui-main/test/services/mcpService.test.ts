import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mcpService } from '@/services/mcpService';

// Mock fetch globally
global.fetch = vi.fn();

describe('MCPService Basic Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should call the correct endpoint when starting server', async () => {
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

  it('should call the correct endpoint when stopping server', async () => {
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

  it('should call the correct endpoint when getting status', async () => {
    const mockStatus = { status: 'running', uptime: 3600, logs: [] };
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockStatus
    });

    const result = await mcpService.getStatus();
    
    expect(fetch).toHaveBeenCalledWith('http://localhost:8080/api/mcp/status');
    expect(result).toEqual(mockStatus);
  });

  it('should handle errors when fetch fails', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ error: 'Internal server error' })
    });

    await expect(mcpService.startServer()).rejects.toThrow('Internal server error');
  });

  it('should create WebSocket with correct URL for log streaming', () => {
    const mockCallback = vi.fn();
    const ws = mcpService.streamLogs(mockCallback);
    
    expect(ws).toBeDefined();
    expect(ws.url).toBe('ws://localhost:8080/api/mcp/logs/stream');
  });
}); 