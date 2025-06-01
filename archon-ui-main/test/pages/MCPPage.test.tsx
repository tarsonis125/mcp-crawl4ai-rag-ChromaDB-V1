import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MCPPage } from '@/pages/MCPPage';
import { mcpService } from '@/services/mcpService';
import { useToast } from '@/contexts/ToastContext';

// Mock the services and contexts
vi.mock('@/services/mcpService');
vi.mock('@/contexts/ToastContext');

describe('MCPPage Basic Tests', () => {
  const mockShowToast = vi.fn();
  
  beforeEach(() => {
    vi.clearAllMocks();
    (useToast as any).mockReturnValue({ showToast: mockShowToast });
    
    // Mock navigator.clipboard
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined)
      }
    });
    
    // Mock all mcpService methods with simple resolved values
    (mcpService.getStatus as any).mockResolvedValue({
      status: 'stopped',
      uptime: null,
      logs: []
    });
    
    (mcpService.getConfiguration as any).mockResolvedValue({
      transport: 'sse',
      host: 'localhost',
      port: 8051
    });
    
    (mcpService.getLogs as any).mockResolvedValue([]);
    (mcpService.streamLogs as any).mockReturnValue({
      close: vi.fn()
    });
    (mcpService.disconnectLogs as any).mockImplementation(() => {});
  });

  it('should render the MCP Dashboard title', async () => {
    render(<MCPPage />);
    // Wait for content to load
    const title = await screen.findByText('MCP Dashboard');
    expect(title).toBeInTheDocument();
  });

  it('should render Server Control section', async () => {
    render(<MCPPage />);
    // Wait for content to load
    const section = await screen.findByText('Server Control');
    expect(section).toBeInTheDocument();
  });

  it('should render Server Logs section', async () => {
    render(<MCPPage />);
    // Wait for content to load
    const section = await screen.findByText('Server Logs');
    expect(section).toBeInTheDocument();
  });

  it('should show loading spinner initially', () => {
    // Mock getStatus to be pending
    (mcpService.getStatus as any).mockReturnValue(new Promise(() => {}));
    
    render(<MCPPage />);
    
    // Check for loading spinner (it's an SVG, not an img role)
    const spinner = document.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
  });

  it('should show start button when server is stopped', async () => {
    render(<MCPPage />);
    // Wait for content to load
    const button = await screen.findByText(/Start Server/i);
    expect(button).toBeInTheDocument();
  });
}); 