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

describe('ADRCard', () => {
  const mockADR: ADR = {
    metadata: {
      id: 'adr-123',
      title: 'Database Selection Decision',
      status: ADRStatus.ACCEPTED,
      author: 'John Doe',
      created_date: '2024-01-15T10:00:00Z',
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
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render ADR card with metadata', () => {
    render(<ADRCard adr={mockADR} {...mockCallbacks} />);

    expect(screen.getByText('Database Selection Decision')).toBeInTheDocument();
    expect(screen.getByText('accepted')).toBeInTheDocument();
    expect(screen.getByText('By John Doe')).toBeInTheDocument();
    expect(screen.getByText('We need to choose a database for our application')).toBeInTheDocument();
  });

  it('should display tags with limit', () => {
    render(<ADRCard adr={mockADR} {...mockCallbacks} />);

    expect(screen.getByText('database')).toBeInTheDocument();
    expect(screen.getByText('postgresql')).toBeInTheDocument();
    expect(screen.getByText('architecture')).toBeInTheDocument();
    expect(screen.getByText('+1 more')).toBeInTheDocument(); // 4 tags, showing 3
  });

  it('should format date correctly', () => {
    render(<ADRCard adr={mockADR} {...mockCallbacks} />);
    
    // Date should be formatted as locale date string
    const dateText = new Date('2024-01-15T10:00:00Z').toLocaleDateString();
    expect(screen.getByText(dateText)).toBeInTheDocument();
  });

  it('should apply correct status color', () => {
    const { rerender } = render(<ADRCard adr={mockADR} {...mockCallbacks} />);
    
    let statusBadge = screen.getByText('accepted');
    expect(statusBadge).toHaveClass('bg-green-100', 'text-green-800');

    // Test different status colors
    const proposedADR = { ...mockADR, metadata: { ...mockADR.metadata, status: ADRStatus.PROPOSED } };
    rerender(<ADRCard adr={proposedADR} {...mockCallbacks} />);
    statusBadge = screen.getByText('proposed');
    expect(statusBadge).toHaveClass('bg-yellow-100', 'text-yellow-800');

    const rejectedADR = { ...mockADR, metadata: { ...mockADR.metadata, status: ADRStatus.REJECTED } };
    rerender(<ADRCard adr={rejectedADR} {...mockCallbacks} />);
    statusBadge = screen.getByText('rejected');
    expect(statusBadge).toHaveClass('bg-red-100', 'text-red-800');
  });

  it('should open modal when View Details is clicked', async () => {
    const user = userEvent.setup();
    render(<ADRCard adr={mockADR} {...mockCallbacks} />);

    await user.click(screen.getByText('View Details'));

    expect(screen.getByTestId('adr-modal')).toBeInTheDocument();
  });

  it('should close modal when close is triggered', async () => {
    const user = userEvent.setup();
    render(<ADRCard adr={mockADR} {...mockCallbacks} />);

    await user.click(screen.getByText('View Details'));
    expect(screen.getByTestId('adr-modal')).toBeInTheDocument();

    await user.click(screen.getByText('Close Modal'));
    expect(screen.queryByTestId('adr-modal')).not.toBeInTheDocument();
  });

  it('should call onAnalyze when Analyze button is clicked', async () => {
    const user = userEvent.setup();
    mockCallbacks.onAnalyze.mockResolvedValue(undefined);
    
    render(<ADRCard adr={mockADR} {...mockCallbacks} />);

    await user.click(screen.getByText('Analyze'));

    expect(mockCallbacks.onAnalyze).toHaveBeenCalledWith('adr-123');
  });

  it('should show analyzing state during analysis', async () => {
    const user = userEvent.setup();
    let resolveAnalyze: () => void;
    const analyzePromise = new Promise<void>((resolve) => {
      resolveAnalyze = resolve;
    });
    mockCallbacks.onAnalyze.mockReturnValue(analyzePromise);

    render(<ADRCard adr={mockADR} {...mockCallbacks} />);

    const analyzeButton = screen.getByText('Analyze');
    await user.click(analyzeButton);

    // Should show analyzing state
    expect(screen.getByText('Analyzing...')).toBeInTheDocument();
    expect(screen.getByText('Analyzing...')).toBeDisabled();

    // Resolve the promise
    resolveAnalyze!();
    await waitFor(() => {
      expect(screen.getByText('Analyze')).toBeInTheDocument();
    });
  });

  it('should call onPushToRAG when Push to RAG button is clicked', async () => {
    const user = userEvent.setup();
    render(<ADRCard adr={mockADR} {...mockCallbacks} />);

    await user.click(screen.getByText('Push to RAG'));

    expect(mockCallbacks.onPushToRAG).toHaveBeenCalledWith('adr-123');
  });

  it('should open delete confirmation modal when Delete is clicked', async () => {
    const user = userEvent.setup();
    render(<ADRCard adr={mockADR} {...mockCallbacks} />);

    await user.click(screen.getByText('Delete'));

    expect(screen.getByTestId('delete-modal')).toBeInTheDocument();
  });

  it('should call onDelete when delete is confirmed', async () => {
    const user = userEvent.setup();
    mockCallbacks.onDelete.mockResolvedValue(undefined);
    
    render(<ADRCard adr={mockADR} {...mockCallbacks} />);

    await user.click(screen.getByText('Delete'));
    await user.click(screen.getByText('Confirm Delete'));

    expect(mockCallbacks.onDelete).toHaveBeenCalledWith('adr-123');
  });

  it('should close delete modal after successful deletion', async () => {
    const user = userEvent.setup();
    mockCallbacks.onDelete.mockResolvedValue(undefined);
    
    render(<ADRCard adr={mockADR} {...mockCallbacks} />);

    await user.click(screen.getByText('Delete'));
    await user.click(screen.getByText('Confirm Delete'));

    await waitFor(() => {
      expect(screen.queryByTestId('delete-modal')).not.toBeInTheDocument();
    });
  });

  it('should handle delete error gracefully', async () => {
    const user = userEvent.setup();
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    mockCallbacks.onDelete.mockRejectedValue(new Error('Delete failed'));
    
    render(<ADRCard adr={mockADR} {...mockCallbacks} />);

    await user.click(screen.getByText('Delete'));
    await user.click(screen.getByText('Confirm Delete'));

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith('Failed to delete ADR');
    });

    alertSpy.mockRestore();
  });

  it('should cancel delete modal when cancel is clicked', async () => {
    const user = userEvent.setup();
    render(<ADRCard adr={mockADR} {...mockCallbacks} />);

    await user.click(screen.getByText('Delete'));
    expect(screen.getByTestId('delete-modal')).toBeInTheDocument();

    await user.click(screen.getByText('Cancel Delete'));
    expect(screen.queryByTestId('delete-modal')).not.toBeInTheDocument();
    expect(mockCallbacks.onDelete).not.toHaveBeenCalled();
  });
});
