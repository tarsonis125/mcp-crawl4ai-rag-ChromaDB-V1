import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MCPPage } from '@/pages/MCPPage';
import { mcpService } from '@/services/mcpService';
import { useToast } from '@/contexts/ToastContext';

// Mock the services and contexts
vi.mock('@/services/mcpService');
vi.mock('@/contexts/ToastContext');

describe('MCPPage Debug', () => {
  const mockShowToast = vi.fn();
  
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    (useToast as any).mockReturnValue({ showToast: mockShowToast });
    
    // Mock navigator.clipboard
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined)
      }
    });
    
    // Mock all mcpService methods
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
      close: vi.fn(),
      onmessage: null,
      onclose: null,
      onerror: null
    });
    (mcpService.disconnectLogs as any).mockImplementation(() => {});
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should render without crashing', async () => {
    const { container } = render(<MCPPage />);
    
    // Wait a bit to see if anything happens
    await waitFor(() => {
      expect(container).toBeTruthy();
    }, { timeout: 1000 });
    
    // Check if getStatus was called
    expect(mcpService.getStatus).toHaveBeenCalled();
  });

  it('should display loading state initially', () => {
    // Mock getStatus to never resolve
    (mcpService.getStatus as any).mockImplementation(() => new Promise(() => {}));
    
    render(<MCPPage />);
    
    // Should show loading spinner
    const spinner = screen.getByRole('img', { hidden: true });
    expect(spinner).toBeInTheDocument();
  });
}); 