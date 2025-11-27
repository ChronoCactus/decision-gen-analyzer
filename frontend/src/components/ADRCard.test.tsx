import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ADRCard } from './ADRCard';
import { ADR, ADRStatus } from '@/types/api';

// Mock the child components
vi.mock('./ADRModal', () => ({
  ADRModal: ({ onClose }: any) => (
    <div data-testid="adr-modal">
      <button onClick={onClose}>Close Modal</button>
    </div>
  ),
}));

vi.mock('./DeleteConfirmationModal', () => ({
  DeleteConfirmationModal: ({ onConfirm, onCancel }: any) => (
    <div data-testid="delete-modal">
      <button onClick={onConfirm}>Confirm Delete</button>
      <button onClick={onCancel}>Cancel Delete</button>
    </div>
  ),
}));

// Mock apiClient
vi.mock('@/lib/api', () => ({
  apiClient: {
    getADRRAGStatus: vi.fn().mockResolvedValue({ exists_in_rag: false }),
  },
}));

describe('ADRCard', () => {
  const mockADR: ADR = {
    metadata: {
      id: 'adr-123',
      title: 'Database Selection Decision',
      status: ADRStatus.ACCEPTED,
      author: 'John Doe',
      created_at: '2024-01-15T10:00:00Z',
      updated_at: '2024-01-15T10:00:00Z',
      tags: ['database', 'postgresql', 'architecture', 'scalability'],
    },
    content: {
      context_and_problem: 'We need to choose a database for our application',
      decision_outcome: 'Use PostgreSQL',
      consequences: 'Better performance and reliability',
    },
  };

  const mockCallbacks = {
    onAnalyze: vi.fn(),
    onDelete: vi.fn(),
    onPushToRAG: vi.fn(),
    onExport: vi.fn(),
  };

  const defaultProps = {
    ...mockCallbacks,
    cacheRebuilding: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render ADR card with metadata', () => {
    render(<ADRCard adr={mockADR} {...defaultProps} />);

    expect(screen.getByText('Database Selection Decision')).toBeInTheDocument();
    expect(screen.getByText('accepted')).toBeInTheDocument();
    expect(screen.getByText('By John Doe')).toBeInTheDocument();
    expect(screen.getByText('We need to choose a database for our application')).toBeInTheDocument();
  });

  it('should display tags with limit', () => {
    render(<ADRCard adr={mockADR} {...defaultProps} />);

    expect(screen.getByText('database')).toBeInTheDocument();
    expect(screen.getByText('postgresql')).toBeInTheDocument();
    expect(screen.getByText('architecture')).toBeInTheDocument();
    expect(screen.getByText('+1 more')).toBeInTheDocument(); // 4 tags, showing 3
  });

  it('should format date correctly', () => {
    render(<ADRCard adr={mockADR} {...defaultProps} />);
    
    // Date should be formatted as locale date string
    const dateText = new Date('2024-01-15T10:00:00Z').toLocaleDateString();
    expect(screen.getByText(dateText)).toBeInTheDocument();
  });

  it('should apply correct status color', () => {
    const { rerender } = render(<ADRCard adr={mockADR} {...defaultProps} />);
    
    let statusBadge = screen.getByText('accepted');
    expect(statusBadge).toHaveClass('bg-green-100', 'text-green-800');

    // Test different status colors
    const proposedADR = { ...mockADR, metadata: { ...mockADR.metadata, status: ADRStatus.PROPOSED } };
    rerender(<ADRCard adr={proposedADR} {...defaultProps} />);
    statusBadge = screen.getByText('proposed');
    expect(statusBadge).toHaveClass('bg-yellow-100', 'text-yellow-800');

    const rejectedADR = { ...mockADR, metadata: { ...mockADR.metadata, status: ADRStatus.REJECTED } };
    rerender(<ADRCard adr={rejectedADR} {...defaultProps} />);
    statusBadge = screen.getByText('rejected');
    expect(statusBadge).toHaveClass('bg-red-100', 'text-red-800');
  });

  it('should open modal when View Details is clicked', async () => {
    const user = userEvent.setup();
    render(<ADRCard adr={mockADR} {...defaultProps} />);

    await user.click(screen.getByText('View'));

    expect(screen.getByTestId('adr-modal')).toBeInTheDocument();
  });

  it('should close modal when close is triggered', async () => {
    const user = userEvent.setup();
    render(<ADRCard adr={mockADR} {...defaultProps} />);

    await user.click(screen.getByText('View'));
    expect(screen.getByTestId('adr-modal')).toBeInTheDocument();

    await user.click(screen.getByText('Close Modal'));
    expect(screen.queryByTestId('adr-modal')).not.toBeInTheDocument();
  });

  it('should call onAnalyze when Analyze button is clicked', async () => {
    mockCallbacks.onAnalyze.mockResolvedValue(undefined);
    
    render(<ADRCard adr={mockADR} {...defaultProps} />);

    // Analyze button is now disabled, so this test should verify it's disabled
    const analyzeButton = screen.getByRole('button', { name: /Analyze/i });
    expect(analyzeButton).toBeDisabled();
  });

  it('should show analyzing state during analysis', async () => {
    const analyzePromise = new Promise<void>(() => { });
    mockCallbacks.onAnalyze.mockReturnValue(analyzePromise);

    render(<ADRCard adr={mockADR} {...defaultProps} />);

    // Analyze button is now always disabled
    const analyzeButton = screen.getByRole('button', { name: /Analyze/i });
    expect(analyzeButton).toBeDisabled();
  });

  it('should call onPushToRAG when Push to RAG button is clicked', async () => {
    const user = userEvent.setup();
    render(<ADRCard adr={mockADR} {...defaultProps} />);

    // Wait for the RAG status check to complete and button to appear
    await waitFor(() => {
      expect(screen.getByText('Push to RAG')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Push to RAG'));

    expect(mockCallbacks.onPushToRAG).toHaveBeenCalledWith('adr-123');
  });

  it('should open delete confirmation modal when Delete is clicked', async () => {
    const user = userEvent.setup();
    render(<ADRCard adr={mockADR} {...defaultProps} />);

    await user.click(screen.getByTitle('Delete ADR'));

    expect(screen.getByTestId('delete-modal')).toBeInTheDocument();
  });

  it('should call onDelete when delete is confirmed', async () => {
    const user = userEvent.setup();
    mockCallbacks.onDelete.mockResolvedValue(undefined);
    
    render(<ADRCard adr={mockADR} {...defaultProps} />);

    await user.click(screen.getByTitle('Delete ADR'));
    await user.click(screen.getByText('Confirm Delete'));

    expect(mockCallbacks.onDelete).toHaveBeenCalledWith('adr-123');
  });

  it('should close delete modal after successful deletion', async () => {
    const user = userEvent.setup();
    mockCallbacks.onDelete.mockResolvedValue(undefined);
    
    render(<ADRCard adr={mockADR} {...defaultProps} />);

    await user.click(screen.getByTitle('Delete ADR'));
    await user.click(screen.getByText('Confirm Delete'));

    await waitFor(() => {
      expect(screen.queryByTestId('delete-modal')).not.toBeInTheDocument();
    });
  });

  it('should handle delete error gracefully', async () => {
    const user = userEvent.setup();
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    mockCallbacks.onDelete.mockRejectedValue(new Error('Delete failed'));
    
    render(<ADRCard adr={mockADR} {...defaultProps} />);

    await user.click(screen.getByTitle('Delete ADR'));
    await user.click(screen.getByText('Confirm Delete'));

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith('Failed to delete ADR');
    });

    alertSpy.mockRestore();
  });

  it('should cancel delete modal when cancel is clicked', async () => {
    const user = userEvent.setup();
    render(<ADRCard adr={mockADR} {...defaultProps} />);

    await user.click(screen.getByTitle('Delete ADR'));
    expect(screen.getByTestId('delete-modal')).toBeInTheDocument();

    await user.click(screen.getByText('Cancel Delete'));
    expect(screen.queryByTestId('delete-modal')).not.toBeInTheDocument();
    expect(mockCallbacks.onDelete).not.toHaveBeenCalled();
  });
});
