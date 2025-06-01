import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MCPPage } from './MCPPage';
import { mcpService } from '../services/mcpService';
import { useToast } from '../contexts/ToastContext';

// Mock the services and contexts
vi.mock('../services/mcpService');
vi.mock('../contexts/ToastContext');

describe('MCPPage', () => {
  const mockShowToast = vi.fn();
  
  beforeEach(() => {
    vi.clearAllMocks();
    (useToast as any).mockReturnValue({ showToast: mockShowToast });
  });

  describe('Server Status Display', () => {
    it('should display server status when stopped', async () => {
      (mcpService.getStatus as any).mockResolvedValue({
        status: 'stopped',
        uptime: null,
        logs: []
      });

      render(<MCPPage />);
      
      await waitFor(() => {
        expect(screen.getByText(/Status: Stopped/i)).toBeInTheDocument();
        expect(screen.getByText(/Start Server/i)).toBeInTheDocument();
        expect(screen.queryByText(/Stop Server/i)).not.toBeInTheDocument();
      });
    });

    it('should display server status when running', async () => {
      (mcpService.getStatus as any).mockResolvedValue({
        status: 'running',
        uptime: 3600,
        logs: ['Server started']
      });

      render(<MCPPage />);
      
      await waitFor(() => {
        expect(screen.getByText(/Status: Running/i)).toBeInTheDocument();
        expect(screen.getByText(/Uptime: 1h 0m 0s/i)).toBeInTheDocument();
        expect(screen.getByText(/Stop Server/i)).toBeInTheDocument();
        expect(screen.queryByText(/Start Server/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Server Control', () => {
    it('should start the server when start button is clicked', async () => {
      (mcpService.getStatus as any).mockResolvedValue({
        status: 'stopped',
        uptime: null,
        logs: []
      });
      
      (mcpService.startServer as any).mockResolvedValue({
        success: true,
        status: 'starting',
        message: 'MCP server is starting'
      });

      render(<MCPPage />);
      
      const startButton = await screen.findByText(/Start Server/i);
      fireEvent.click(startButton);
      
      await waitFor(() => {
        expect(mcpService.startServer).toHaveBeenCalled();
        expect(mockShowToast).toHaveBeenCalledWith('MCP server is starting', 'success');
      });
    });

    it('should stop the server when stop button is clicked', async () => {
      (mcpService.getStatus as any).mockResolvedValue({
        status: 'running',
        uptime: 3600,
        logs: []
      });
      
      (mcpService.stopServer as any).mockResolvedValue({
        success: true,
        status: 'stopped',
        message: 'MCP server stopped'
      });

      render(<MCPPage />);
      
      const stopButton = await screen.findByText(/Stop Server/i);
      fireEvent.click(stopButton);
      
      await waitFor(() => {
        expect(mcpService.stopServer).toHaveBeenCalled();
        expect(mockShowToast).toHaveBeenCalledWith('MCP server stopped', 'success');
      });
    });

    it('should show error toast on server start failure', async () => {
      (mcpService.getStatus as any).mockResolvedValue({
        status: 'stopped',
        uptime: null,
        logs: []
      });
      
      (mcpService.startServer as any).mockRejectedValue(new Error('Failed to start server'));

      render(<MCPPage />);
      
      const startButton = await screen.findByText(/Start Server/i);
      fireEvent.click(startButton);
      
      await waitFor(() => {
        expect(mockShowToast).toHaveBeenCalledWith('Failed to start server', 'error');
      });
    });
  });

  describe('Log Display', () => {
    it('should display server logs', async () => {
      const mockLogs = [
        '[INFO] MCP Server initialization...',
        '[INFO] Loading configuration from /etc/mcp/config.json',
        '[INFO] Server ready to start'
      ];
      
      (mcpService.getStatus as any).mockResolvedValue({
        status: 'running',
        uptime: 60,
        logs: mockLogs
      });

      render(<MCPPage />);
      
      await waitFor(() => {
        mockLogs.forEach(log => {
          expect(screen.getByText(log)).toBeInTheDocument();
        });
      });
    });

    it('should stream logs in real-time when server is running', async () => {
      const mockWebSocket = {
        close: vi.fn(),
        onmessage: null as ((event: MessageEvent) => void) | null,
        onclose: null as ((event: CloseEvent) => void) | null,
        onerror: null as ((event: Event) => void) | null
      };
      
      (mcpService.getStatus as any).mockResolvedValue({
        status: 'running',
        uptime: 60,
        logs: []
      });
      
      (mcpService.streamLogs as any).mockReturnValue(mockWebSocket);

      render(<MCPPage />);
      
      await waitFor(() => {
        expect(mcpService.streamLogs).toHaveBeenCalled();
      });
      
      // Simulate incoming log message
      const newLog = { 
        timestamp: '2024-01-20T10:00:00Z', 
        level: 'INFO', 
        message: 'New log message' 
      };
      
      if (mockWebSocket.onmessage) {
        mockWebSocket.onmessage({ data: JSON.stringify(newLog) } as MessageEvent);
      }
      
      await waitFor(() => {
        expect(screen.getByText(/\[INFO\] New log message/)).toBeInTheDocument();
      });
    });

    it('should clear logs when clear button is clicked', async () => {
      (mcpService.getStatus as any).mockResolvedValue({
        status: 'running',
        uptime: 60,
        logs: ['Log 1', 'Log 2']
      });
      
      (mcpService.clearLogs as any).mockResolvedValue({
        success: true,
        message: 'Logs cleared'
      });

      render(<MCPPage />);
      
      const clearButton = await screen.findByText(/Clear Logs/i);
      fireEvent.click(clearButton);
      
      await waitFor(() => {
        expect(mcpService.clearLogs).toHaveBeenCalled();
        expect(screen.queryByText('Log 1')).not.toBeInTheDocument();
        expect(screen.queryByText('Log 2')).not.toBeInTheDocument();
      });
    });
  });

  describe('Connection Details', () => {
    it('should display connection details when server is running', async () => {
      (mcpService.getStatus as any).mockResolvedValue({
        status: 'running',
        uptime: 60,
        logs: []
      });
      
      (mcpService.getConfiguration as any).mockResolvedValue({
        transport: 'sse',
        host: 'localhost',
        port: 8051
      });

      render(<MCPPage />);
      
      await waitFor(() => {
        expect(screen.getByText(/Connection Details/i)).toBeInTheDocument();
        expect(screen.getByText(/Transport: sse/i)).toBeInTheDocument();
        expect(screen.getByText(/URL: http:\/\/localhost:8051\/sse/i)).toBeInTheDocument();
      });
    });

    it('should show copy button for connection config', async () => {
      (mcpService.getStatus as any).mockResolvedValue({
        status: 'running',
        uptime: 60,
        logs: []
      });
      
      (mcpService.getConfiguration as any).mockResolvedValue({
        transport: 'sse',
        host: 'localhost',
        port: 8051
      });

      render(<MCPPage />);
      
      const copyButton = await screen.findByText(/Copy Config/i);
      fireEvent.click(copyButton);
      
      await waitFor(() => {
        expect(mockShowToast).toHaveBeenCalledWith('Configuration copied to clipboard', 'success');
      });
    });
  });

  describe('Auto-refresh', () => {
    it('should poll for status updates', async () => {
      (mcpService.getStatus as any).mockResolvedValue({
        status: 'running',
        uptime: 60,
        logs: []
      });

      render(<MCPPage />);
      
      await waitFor(() => {
        expect(mcpService.getStatus).toHaveBeenCalledTimes(1);
      });
      
      // Wait for auto-refresh (assuming 5 second interval)
      vi.advanceTimersByTime(5000);
      
      await waitFor(() => {
        expect(mcpService.getStatus).toHaveBeenCalledTimes(2);
      });
    });

    it('should stop polling when component unmounts', async () => {
      (mcpService.getStatus as any).mockResolvedValue({
        status: 'running',
        uptime: 60,
        logs: []
      });
      
      const { unmount } = render(<MCPPage />);
      
      await waitFor(() => {
        expect(mcpService.getStatus).toHaveBeenCalledTimes(1);
      });
      
      unmount();
      
      // Advance timers after unmount
      vi.advanceTimersByTime(5000);
      
      // Should not have made additional calls
      expect(mcpService.getStatus).toHaveBeenCalledTimes(1);
    });
  });
}); 