import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ADRModal } from './ADRModal';
import { ADR, ADRStatus } from '@/types/api';

// Mock the child components and hooks
vi.mock('./PersonasModal', () => ({
  PersonasModal: () => <div data-testid="personas-modal">Personas Modal</div>,
}));

vi.mock('@/hooks/useEscapeKey', () => ({
  useEscapeKey: vi.fn(),
}));

// Mock the API client
vi.mock('@/lib/api', () => ({
  apiClient: {
    updateADRStatus: vi.fn(),
  },
}));

describe('ADRModal', () => {
  const mockADR: ADR = {
    metadata: {
      id: 'adr-123',
      title: 'Database Selection',
      status: ADRStatus.ACCEPTED,
      author: 'John Doe',
      created_at: '2024-01-15T10:00:00Z',
      updated_at: '2024-01-15T10:00:00Z',
      tags: ['database', 'architecture'],
    },
    content: {
      context_and_problem: 'We need a database',
      decision_outcome: 'Use PostgreSQL',
      consequences: 'Good performance',
      considered_options: ['PostgreSQL', 'MySQL', 'MongoDB'],
      decision_drivers: ['ACID compliance', 'Performance'],
      consequences_structured: {
        positive: ['Better performance', 'ACID compliance'],
        negative: ['Higher resource usage'],
      },
    },
  };

  const mockProps = {
    adr: mockADR,
    onClose: vi.fn(),
    onAnalyze: vi.fn(),
    isAnalyzing: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render ADR modal with title and metadata', () => {
    render(<ADRModal {...mockProps} />);

    expect(screen.getByText('Database Selection')).toBeInTheDocument();
    expect(screen.getByText('By John Doe')).toBeInTheDocument();
    expect(screen.getByText('accepted')).toBeInTheDocument();
  });

  it('should display context and problem section', () => {
    render(<ADRModal {...mockProps} />);

    expect(screen.getByText('Context & Problem')).toBeInTheDocument();
    expect(screen.getByText('We need a database')).toBeInTheDocument();
  });

  it('should display decision outcome section', () => {
    render(<ADRModal {...mockProps} />);

    expect(screen.getByText('Decision Outcome')).toBeInTheDocument();
    expect(screen.getByText('Use PostgreSQL')).toBeInTheDocument();
  });

  it('should display structured consequences', () => {
    render(<ADRModal {...mockProps} />);

    expect(screen.getByText('✓ Positive')).toBeInTheDocument();
    expect(screen.getByText('Better performance')).toBeInTheDocument();
    // "ACID compliance" appears in both consequences and decision drivers
    expect(screen.getAllByText('ACID compliance').length).toBeGreaterThan(0);

    expect(screen.getByText('✗ Negative')).toBeInTheDocument();
    expect(screen.getByText('Higher resource usage')).toBeInTheDocument();
  });

  it('should display plain text consequences when structured is not available', () => {
    const adrWithPlainConsequences = {
      ...mockADR,
      content: {
        ...mockADR.content,
        consequences_structured: undefined,
      },
    };

    render(<ADRModal {...mockProps} adr={adrWithPlainConsequences} />);

    expect(screen.getByText('Good performance')).toBeInTheDocument();
  });

  it('should call onClose when close button is clicked', async () => {
    const user = userEvent.setup();
    render(<ADRModal {...mockProps} />);

    const closeButton = screen.getByText('×');
    await user.click(closeButton);

    expect(mockProps.onClose).toHaveBeenCalledTimes(1);
  });

  it('should call onAnalyze when analyze button is clicked', async () => {
    const user = userEvent.setup();
    render(<ADRModal {...mockProps} />);

    const analyzeButton = screen.getByText('Analyze ADR');
    await user.click(analyzeButton);

    expect(mockProps.onAnalyze).toHaveBeenCalledTimes(1);
  });

  it('should show analyzing state when isAnalyzing is true', () => {
    render(<ADRModal {...mockProps} isAnalyzing={true} />);

    expect(screen.getByText('Analyzing...')).toBeInTheDocument();
  });

  it('should disable analyze button when isAnalyzing is true', () => {
    render(<ADRModal {...mockProps} isAnalyzing={true} />);

    const analyzeButton = screen.getByText('Analyzing...');
    expect(analyzeButton).toBeDisabled();
  });

  it('should apply correct status colors', () => {
    render(<ADRModal {...mockProps} />);

    // Status is now a select dropdown with color classes
    const statusSelect = screen.getByRole('combobox');
    expect(statusSelect).toHaveValue('accepted');
    // Check that it has the green color classes for accepted status
    expect(statusSelect.className).toContain('bg-green-100');
    expect(statusSelect.className).toContain('text-green-800');
  });

  it('should display tags when present', () => {
    render(<ADRModal {...mockProps} />);

    expect(screen.getByText('database')).toBeInTheDocument();
    expect(screen.getByText('architecture')).toBeInTheDocument();
  });

  it('should display considered options when present', () => {
    render(<ADRModal {...mockProps} />);

    // PostgreSQL appears in both decision outcome and options list
    expect(screen.getAllByText(/PostgreSQL/).length).toBeGreaterThan(0);
    expect(screen.getByText(/MySQL/)).toBeInTheDocument();
    expect(screen.getByText(/MongoDB/)).toBeInTheDocument();
  });

  it('should display decision drivers when present', () => {
    render(<ADRModal {...mockProps} />);

    // "ACID compliance" appears in multiple places, so use getAllByText
    expect(screen.getAllByText(/ACID compliance/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Performance/)).toBeInTheDocument();
  });

  it('should format date correctly', () => {
    render(<ADRModal {...mockProps} />);

    const dateText = new Date('2024-01-15T10:00:00Z').toLocaleDateString();
    expect(screen.getByText(dateText)).toBeInTheDocument();
  });

  it('should render status dropdown with all status options', () => {
    render(<ADRModal {...mockProps} />);

    const statusSelect = screen.getByRole('combobox');
    expect(statusSelect).toBeInTheDocument();
    
    // Check all options are present
    const options = screen.getAllByRole('option');
    expect(options).toHaveLength(5);
    expect(screen.getByRole('option', { name: 'proposed' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'accepted' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'rejected' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'deprecated' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'superseded' })).toBeInTheDocument();
  });

  it('should call API and update status when dropdown value changes', async () => {
    const { apiClient } = await import('@/lib/api');
    const mockUpdateStatus = vi.mocked(apiClient.updateADRStatus);
    const updatedADR = { ...mockADR, metadata: { ...mockADR.metadata, status: ADRStatus.DEPRECATED } };
    mockUpdateStatus.mockResolvedValue({ message: 'Status updated', adr: updatedADR });

    const user = userEvent.setup();
    render(<ADRModal {...mockProps} />);

    const statusSelect = screen.getByRole('combobox');
    expect(statusSelect).toHaveValue('accepted');

    // Change status to deprecated
    await user.selectOptions(statusSelect, 'deprecated');

    // Should call API with correct parameters
    expect(mockUpdateStatus).toHaveBeenCalledWith('adr-123', 'deprecated');

    // Status should be updated in the UI
    expect(statusSelect).toHaveValue('deprecated');
  });

  it('should call onADRUpdate callback when status changes', async () => {
    const { apiClient } = await import('@/lib/api');
    const mockUpdateStatus = vi.mocked(apiClient.updateADRStatus);
    const updatedADR = { ...mockADR, metadata: { ...mockADR.metadata, status: ADRStatus.REJECTED } };
    mockUpdateStatus.mockResolvedValue({ message: 'Status updated', adr: updatedADR });

    const mockOnADRUpdate = vi.fn();
    const user = userEvent.setup();
    render(<ADRModal {...mockProps} onADRUpdate={mockOnADRUpdate} />);

    const statusSelect = screen.getByRole('combobox');
    await user.selectOptions(statusSelect, 'rejected');

    // Wait for the update to complete
    await vi.waitFor(() => {
      expect(mockOnADRUpdate).toHaveBeenCalledWith(updatedADR);
    });
  });

  it('should disable status dropdown while updating', async () => {
    const { apiClient } = await import('@/lib/api');
    const mockUpdateStatus = vi.mocked(apiClient.updateADRStatus);
    
    // Make the API call take some time
    mockUpdateStatus.mockImplementation(() => new Promise(resolve => {
      setTimeout(() => resolve({ 
        message: 'Status updated', 
        adr: { ...mockADR, metadata: { ...mockADR.metadata, status: ADRStatus.PROPOSED } }
      }), 100);
    }));

    const user = userEvent.setup();
    render(<ADRModal {...mockProps} />);

    const statusSelect = screen.getByRole('combobox');
    
    // Start changing status
    await user.selectOptions(statusSelect, 'proposed');

    // Select should be disabled during update
    expect(statusSelect).toBeDisabled();

    // Wait for update to complete
    await vi.waitFor(() => {
      expect(statusSelect).not.toBeDisabled();
    });
  });

  it('should handle status update errors gracefully', async () => {
    const { apiClient } = await import('@/lib/api');
    const mockUpdateStatus = vi.mocked(apiClient.updateADRStatus);
    mockUpdateStatus.mockRejectedValue(new Error('Network error'));

    // Mock window.alert
    const mockAlert = vi.spyOn(window, 'alert').mockImplementation(() => {});

    const user = userEvent.setup();
    render(<ADRModal {...mockProps} />);

    const statusSelect = screen.getByRole('combobox');
    await user.selectOptions(statusSelect, 'proposed');

    // Should show error alert
    await vi.waitFor(() => {
      expect(mockAlert).toHaveBeenCalledWith('Failed to update ADR status. Please try again.');
    });

    // Status should remain unchanged
    expect(statusSelect).toHaveValue('accepted');

    mockAlert.mockRestore();
  });

  it('should not make API call if status is unchanged', async () => {
    const { apiClient } = await import('@/lib/api');
    const mockUpdateStatus = vi.mocked(apiClient.updateADRStatus);

    const user = userEvent.setup();
    render(<ADRModal {...mockProps} />);

    const statusSelect = screen.getByRole('combobox');
    
    // Select the same status (already 'accepted')
    await user.selectOptions(statusSelect, 'accepted');

    // Should not call API
    expect(mockUpdateStatus).not.toHaveBeenCalled();
  });
});
