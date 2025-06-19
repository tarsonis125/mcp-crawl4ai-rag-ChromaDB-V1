import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CrawlingProgressCard } from '@/components/knowledge-base/CrawlingProgressCard';
import { CrawlProgressData } from '@/services/crawlProgressServiceV2';

// Mock WebSocket for testing
const mockWebSocket = {
  send: vi.fn(),
  close: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  readyState: 1,
  onopen: null,
  onmessage: null,
  onclose: null,
  onerror: null
};

vi.stubGlobal('WebSocket', vi.fn(() => mockWebSocket));

// Helper function to create mock progress data
const createMockProgressData = (overrides: Partial<CrawlProgressData> = {}): CrawlProgressData => ({
  progressId: 'test-progress-123',
  status: 'crawling',
  percentage: 45,
  currentUrl: 'https://docs.example.com/page-5',
  eta: '2 minutes remaining',
  totalPages: 20,
  processedPages: 9,
  logs: [
    'Starting crawl of https://docs.example.com',
    'Processing page 1/20: https://docs.example.com/intro',
    'Processing page 9/20: https://docs.example.com/page-5'
  ],
  ...overrides
});

describe('Crawling Progress Implementation Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('CrawlingProgressCard Component', () => {

    it('renders crawling state with all progress information', () => {
      const progressData = createMockProgressData();
      const mockOnComplete = vi.fn();
      const mockOnError = vi.fn();

      render(
        <CrawlingProgressCard 
          progressData={progressData}
          onComplete={mockOnComplete}
          onError={mockOnError}
        />
      );

      // Check for key progress indicators
      expect(screen.getByText('Crawling in progress...')).toBeInTheDocument();
      expect(screen.getByText('45%')).toBeInTheDocument();
      expect(screen.getByText('9 of 20 pages processed')).toBeInTheDocument();
      expect(screen.getByText('https://docs.example.com/page-5')).toBeInTheDocument();
    });

    it('renders completed state with final results', () => {
      const completedData = createMockProgressData({
        status: 'completed',
        percentage: 100,
        processedPages: 20,
        chunksStored: 185,
        wordCount: 45000,
        duration: '3 minutes 25 seconds'
      });

      render(
        <CrawlingProgressCard 
          progressData={completedData}
          onComplete={vi.fn()}
          onError={vi.fn()}
        />
      );

      expect(screen.getByText('Crawling completed!')).toBeInTheDocument();
      expect(screen.getByText('100%')).toBeInTheDocument();
      expect(screen.getByText('185 chunks stored')).toBeInTheDocument();
      expect(screen.getByText('45,000 words processed')).toBeInTheDocument();
      // Check for duration text (accounting for spacing in rendered HTML)
      expect(screen.getByText(/3 minutes 25 seconds/)).toBeInTheDocument();
    });

    it('renders error state with retry option', () => {
      const errorData = createMockProgressData({
        status: 'error',
        error: 'Failed to connect to https://docs.example.com',
        percentage: 25
      });

      const mockOnError = vi.fn();
      const mockOnRetry = vi.fn();

      render(
        <CrawlingProgressCard 
          progressData={errorData}
          onComplete={vi.fn()}
          onError={mockOnError}
          onRetry={mockOnRetry}
        />
      );

      expect(screen.getByText('Crawling failed')).toBeInTheDocument();
      expect(screen.getByText('Failed to connect to https://docs.example.com')).toBeInTheDocument();
      
      const retryButton = screen.getByRole('button', { name: /retry/i });
      expect(retryButton).toBeInTheDocument();
      
      fireEvent.click(retryButton);
      expect(mockOnRetry).toHaveBeenCalled();
    });

    it('toggles log visibility when console output button is clicked', () => {
      const progressData = createMockProgressData();

      render(
        <CrawlingProgressCard 
          progressData={progressData}
          onComplete={vi.fn()}
          onError={vi.fn()}
        />
      );

      // Logs should be hidden initially
      expect(screen.queryByText('Starting crawl of https://docs.example.com')).not.toBeInTheDocument();

      // Click to show logs
      const toggleButton = screen.getByRole('button', { name: /view console output/i });
      fireEvent.click(toggleButton);

      // Logs should now be visible
      expect(screen.getByText('Starting crawl of https://docs.example.com')).toBeInTheDocument();
      expect(screen.getByText('Processing page 9/20: https://docs.example.com/page-5')).toBeInTheDocument();
    });

    it('displays completed status without automatically calling onComplete', () => {
      const mockOnComplete = vi.fn();
      const completedData = createMockProgressData({
        status: 'completed',
        percentage: 100
      });

      render(
        <CrawlingProgressCard 
          progressData={completedData}
          onComplete={mockOnComplete}
          onError={vi.fn()}
        />
      );

      // Component should display completed status
      expect(screen.getByText('Crawling completed!')).toBeInTheDocument();
      // onComplete is called by parent component managing progress, not by this component
      expect(mockOnComplete).not.toHaveBeenCalled();
    });

    it('displays error status without automatically calling onError', () => {
      const mockOnError = vi.fn();
      const errorData = createMockProgressData({
        status: 'error',
        error: 'Connection timeout'
      });

      render(
        <CrawlingProgressCard 
          progressData={errorData}
          onComplete={vi.fn()}
          onError={mockOnError}
        />
      );

      // Component should display error status
      expect(screen.getByText('Crawling failed')).toBeInTheDocument();
      expect(screen.getByText('Connection timeout')).toBeInTheDocument();
      // onError is called by parent component managing progress, not by this component
      expect(mockOnError).not.toHaveBeenCalled();
    });

    it('displays different status indicators for each state', () => {
      const states: Array<{ status: CrawlProgressData['status'], expectedText: string }> = [
        { status: 'starting', expectedText: 'Starting crawl...' },
        { status: 'crawling', expectedText: 'Crawling in progress...' },
        { status: 'completed', expectedText: 'Crawling completed!' },
        { status: 'error', expectedText: 'Crawling failed' }
      ];

      states.forEach(({ status, expectedText }) => {
        const { unmount } = render(
          <CrawlingProgressCard 
            progressData={createMockProgressData({ status })}
            onComplete={vi.fn()}
            onError={vi.fn()}
          />
        );

        expect(screen.getByText(expectedText)).toBeInTheDocument();
        unmount();
      });
    });
  });

  describe('Progress Data Validation', () => {
    it('handles missing optional fields gracefully', () => {
      const minimalData: CrawlProgressData = {
        progressId: 'test-123',
        status: 'starting',
        percentage: 0,
        logs: []
      };

      render(
        <CrawlingProgressCard 
          progressData={minimalData}
          onComplete={vi.fn()}
          onError={vi.fn()}
        />
      );

      expect(screen.getByText('Starting crawl...')).toBeInTheDocument();
      expect(screen.getByText('0%')).toBeInTheDocument();
    });

    it('displays progress percentage correctly across range', () => {
      const percentages = [0, 25, 50, 75, 100];
      
      percentages.forEach(percentage => {
        const { unmount } = render(
          <CrawlingProgressCard 
            progressData={createMockProgressData({ percentage })}
            onComplete={vi.fn()}
            onError={vi.fn()}
          />
        );

        expect(screen.getByText(`${percentage}%`)).toBeInTheDocument();
        unmount();
      });
    });
  });

  describe('WebSocket Service Integration', () => {
    it('creates WebSocket connection with correct URL format', async () => {
      // Import the real service
      const { crawlProgressService } = await import('@/services/crawlProgressService');
      
      const progressId = 'test-progress-456';
      crawlProgressService.connect(progressId);

      expect(global.WebSocket).toHaveBeenCalledWith(
        'ws://localhost:8080/api/crawl-progress/test-progress-456'
      );
    });

    it('properly cleans up WebSocket connection on disconnect', async () => {
      const { crawlProgressService } = await import('@/services/crawlProgressService');
      
      crawlProgressService.connect('test-progress');
      crawlProgressService.disconnect();

      expect(mockWebSocket.close).toHaveBeenCalled();
    });
  });

  describe('Component Behavior with Real Props', () => {
    it('updates display when progress data changes', () => {
      const initialData = createMockProgressData({ percentage: 25, processedPages: 5 });
      
      const { rerender } = render(
        <CrawlingProgressCard 
          progressData={initialData}
          onComplete={vi.fn()}
          onError={vi.fn()}
        />
      );

      expect(screen.getByText('25%')).toBeInTheDocument();
      expect(screen.getByText('5 of 20 pages processed')).toBeInTheDocument();

      // Update progress
      const updatedData = createMockProgressData({ percentage: 75, processedPages: 15 });
      
      rerender(
        <CrawlingProgressCard 
          progressData={updatedData}
          onComplete={vi.fn()}
          onError={vi.fn()}
        />
      );

      expect(screen.getByText('75%')).toBeInTheDocument();
      expect(screen.getByText('15 of 20 pages processed')).toBeInTheDocument();
    });

    it('maintains log history when new logs are added', () => {
      const initialData = createMockProgressData({
        logs: ['Starting crawl...', 'Processing page 1/20']
      });
      
      const { rerender } = render(
        <CrawlingProgressCard 
          progressData={initialData}
          onComplete={vi.fn()}
          onError={vi.fn()}
        />
      );

      // Expand logs
      fireEvent.click(screen.getByRole('button', { name: /view console output/i }));
      expect(screen.getByText('Starting crawl...')).toBeInTheDocument();

      // Add more logs
      const updatedData = createMockProgressData({
        logs: ['Starting crawl...', 'Processing page 1/20', 'Processing page 10/20', 'Almost done...']
      });
      
      rerender(
        <CrawlingProgressCard 
          progressData={updatedData}
          onComplete={vi.fn()}
          onError={vi.fn()}
        />
      );

      // All logs should be visible
      expect(screen.getByText('Starting crawl...')).toBeInTheDocument();
      expect(screen.getByText('Almost done...')).toBeInTheDocument();
    });
  });
});