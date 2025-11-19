import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueueViewerModal } from './QueueViewerModal';
import { apiClient } from '@/lib/api';

// Mock the API client
vi.mock('@/lib/api', () => ({
  apiClient: {
    getQueueTasks: vi.fn(),
    cancelTask: vi.fn(),
    cleanupOrphanedTasks: vi.fn(),
    clearQueue: vi.fn(),
  },
}));

// Mock the useTaskQueueWebSocket hook
vi.mock('@/hooks/useTaskQueueWebSocket', () => ({
  useTaskQueueWebSocket: () => ({
    trackedTasks: new Map(),
  }),
}));

// Mock the useEscapeKey hook
vi.mock('@/hooks/useEscapeKey', () => ({
  useEscapeKey: vi.fn(),
}));

describe('QueueViewerModal - Queue Management', () => {
  const mockOnClose = vi.fn();
  
  const defaultProps = {
    onClose: mockOnClose,
    totalTasks: 3,
    activeTasks: 2,
    pendingTasks: 1,
    workersOnline: 1,
  };

  const mockTasks = [
    {
      task_id: 'task-1',
      task_name: 'generate_adr_task',
      status: 'active',
      position: null,
      args: [],
      kwargs: { personas: ['technical_lead'] },
      worker: 'worker-1',
      started_at: Date.now() / 1000 - 60,
      eta: null,
    },
    {
      task_id: 'task-2',
      task_name: 'analyze_adr_task',
      status: 'pending',
      position: 0,
      args: [],
      kwargs: {},
      worker: null,
      started_at: null,
      eta: null,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (apiClient.getQueueTasks as any).mockResolvedValue({ tasks: mockTasks });
  });

  describe('Cleanup Orphaned Tasks', () => {
    it('should render cleanup orphaned button', () => {
      render(<QueueViewerModal {...defaultProps} />);
      
      expect(screen.getByText('Cleanup Orphaned')).toBeInTheDocument();
    });

    it('should show confirmation dialog when cleanup orphaned is clicked', async () => {
      const user = userEvent.setup();
      render(<QueueViewerModal {...defaultProps} />);
      
      const cleanupButton = screen.getByText('Cleanup Orphaned');
      await user.click(cleanupButton);
      
      expect(screen.getByText('Cleanup Orphaned Tasks?')).toBeInTheDocument();
      expect(screen.getByText(/This will remove task records in Redis/)).toBeInTheDocument();
    });

    it('should cancel cleanup when cancel button is clicked in dialog', async () => {
      const user = userEvent.setup();
      render(<QueueViewerModal {...defaultProps} />);
      
      // Open confirmation dialog
      await user.click(screen.getByText('Cleanup Orphaned'));
      
      // Click cancel in dialog
      const cancelButtons = screen.getAllByText('Cancel');
      await user.click(cancelButtons[cancelButtons.length - 1]);
      
      // Dialog should close without calling API
      await waitFor(() => {
        expect(screen.queryByText('Cleanup Orphaned Tasks?')).not.toBeInTheDocument();
      });
      expect(apiClient.cleanupOrphanedTasks).not.toHaveBeenCalled();
    });

    it('should call cleanup API and show success message', async () => {
      const user = userEvent.setup();
      (apiClient.cleanupOrphanedTasks as any).mockResolvedValue({
        cleaned_count: 3,
        error_count: 0,
        cleaned_tasks: [],
        errors: [],
      });

      render(<QueueViewerModal {...defaultProps} />);
      
      // Open confirmation dialog and confirm
      await user.click(screen.getByText('Cleanup Orphaned'));
      await user.click(screen.getByText('Confirm'));
      
      await waitFor(() => {
        expect(apiClient.cleanupOrphanedTasks).toHaveBeenCalledOnce();
        expect(screen.getByText('✅ Cleaned 3 orphaned tasks')).toBeInTheDocument();
      });
    });

    it('should handle cleanup errors gracefully', async () => {
      const user = userEvent.setup();
      (apiClient.cleanupOrphanedTasks as any).mockRejectedValue(new Error('Connection failed'));

      render(<QueueViewerModal {...defaultProps} />);
      
      await user.click(screen.getByText('Cleanup Orphaned'));
      await user.click(screen.getByText('Confirm'));
      
      await waitFor(() => {
        expect(screen.getByText('❌ Failed to cleanup: Connection failed')).toBeInTheDocument();
      });
    });
  });

  describe('Clear Queue', () => {
    it('should render clear queue button', () => {
      render(<QueueViewerModal {...defaultProps} />);
      
      expect(screen.getByText('Clear Queue')).toBeInTheDocument();
    });

    it('should disable clear queue button when queue is empty', () => {
      render(<QueueViewerModal {...defaultProps} totalTasks={0} />);
      
      const clearButton = screen.getByText('Clear Queue');
      expect(clearButton).toBeDisabled();
    });

    it('should show confirmation dialog when clear queue is clicked', async () => {
      const user = userEvent.setup();
      render(<QueueViewerModal {...defaultProps} />);
      
      const clearButton = screen.getByText('Clear Queue');
      await user.click(clearButton);
      
      expect(screen.getByText('Clear Entire Queue?')).toBeInTheDocument();
      expect(screen.getByText(/This will cancel all pending tasks/)).toBeInTheDocument();
    });

    it('should call clear queue API and show success message', async () => {
      const user = userEvent.setup();
      (apiClient.clearQueue as any).mockResolvedValue({
        revoked_active: 2,
        purged_pending: 3,
        cleared_redis_records: 1,
        error_count: 0,
        revoked_tasks: [],
        errors: [],
      });

      render(<QueueViewerModal {...defaultProps} />);
      
      await user.click(screen.getByText('Clear Queue'));
      await user.click(screen.getByText('Confirm'));
      
      await waitFor(() => {
        expect(apiClient.clearQueue).toHaveBeenCalledWith(false);
        expect(screen.getByText('✅ Cleared queue: 2 active + 3 pending tasks')).toBeInTheDocument();
      });
    });

    it('should handle clear queue errors', async () => {
      const user = userEvent.setup();
      (apiClient.clearQueue as any).mockRejectedValue(new Error('Redis error'));

      render(<QueueViewerModal {...defaultProps} />);
      
      await user.click(screen.getByText('Clear Queue'));
      await user.click(screen.getByText('Confirm'));
      
      await waitFor(() => {
        expect(screen.getByText('❌ Failed to clear queue: Redis error')).toBeInTheDocument();
      });
    });
  });

  describe('Cancel Individual Task', () => {
    it('should render cancel button for each task', async () => {
      render(<QueueViewerModal {...defaultProps} />);
      
      await waitFor(() => {
        const cancelButtons = screen.getAllByText('Cancel');
        // One in confirmation dialog area, rest are task cancel buttons
        expect(cancelButtons.length).toBeGreaterThan(1);
      });
    });

    it('should show confirmation dialog when task cancel is clicked', async () => {
      const user = userEvent.setup();
      render(<QueueViewerModal {...defaultProps} />);
      
      await waitFor(() => {
        expect(screen.getByText('Generate ADR')).toBeInTheDocument();
      });
      
      // Find cancel buttons by title attribute
      const cancelButtons = screen.getAllByTitle('Cancel this task');
      await user.click(cancelButtons[0]);
      
      expect(screen.getByText(/Cancel Task:/)).toBeInTheDocument();
    });

    it('should call cancel task API and refresh list', async () => {
      const user = userEvent.setup();
      (apiClient.cancelTask as any).mockResolvedValue({
        message: 'Task cancelled',
        task_id: 'task-1',
        cancelled: true,
      });

      render(<QueueViewerModal {...defaultProps} />);
      
      await waitFor(() => {
        expect(screen.getByText('Generate ADR')).toBeInTheDocument();
      });
      
      // Click cancel on first task - find by title attribute
      const cancelButtons = screen.getAllByTitle('Cancel this task');
      await user.click(cancelButtons[0]);
      
      // Confirm cancellation
      await user.click(screen.getByText('Confirm'));
      
      await waitFor(() => {
        // task-1 has status 'active', so terminate should be true
        expect(apiClient.cancelTask).toHaveBeenCalledWith('task-1', true);
        expect(screen.getByText('✅ Task cancelled successfully')).toBeInTheDocument();
        // Should refetch tasks
        expect(apiClient.getQueueTasks).toHaveBeenCalled();
      });
    });

    it('should handle cancel task errors', async () => {
      const user = userEvent.setup();
      (apiClient.cancelTask as any).mockRejectedValue(new Error('Task not found'));

      render(<QueueViewerModal {...defaultProps} />);
      
      await waitFor(() => {
        expect(screen.getByText('Generate ADR')).toBeInTheDocument();
      });
      
      // Find cancel buttons by title attribute
      const cancelButtons = screen.getAllByTitle('Cancel this task');
      await user.click(cancelButtons[0]);
      await user.click(screen.getByText('Confirm'));
      
      await waitFor(() => {
        expect(screen.getByText('❌ Failed to cancel task: Task not found')).toBeInTheDocument();
      });
    });
  });

  describe('Action Loading States', () => {
    it('should disable buttons while action is in progress', async () => {
      const user = userEvent.setup();
      // Make API call hang
      (apiClient.cleanupOrphanedTasks as any).mockImplementation(() => 
        new Promise(resolve => setTimeout(resolve, 1000))
      );

      render(<QueueViewerModal {...defaultProps} />);
      
      await user.click(screen.getByText('Cleanup Orphaned'));
      await user.click(screen.getByText('Confirm'));
      
      // Buttons should be disabled during action
      await waitFor(() => {
        expect(screen.getByText('Cleanup Orphaned')).toBeDisabled();
        expect(screen.getByText('Clear Queue')).toBeDisabled();
      });
    });

    it('should show processing text in confirmation dialog', async () => {
      const user = userEvent.setup();
      (apiClient.cleanupOrphanedTasks as any).mockImplementation(() => 
        new Promise(resolve => setTimeout(resolve, 1000))
      );

      render(<QueueViewerModal {...defaultProps} />);
      
      await user.click(screen.getByText('Cleanup Orphaned'));
      await user.click(screen.getByText('Confirm'));
      
      await waitFor(() => {
        expect(screen.getByText('Processing...')).toBeInTheDocument();
      });
    });
  });
});
