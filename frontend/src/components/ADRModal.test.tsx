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

  const mockADRWithPersonas: ADR = {
    ...mockADR,
    persona_responses: [
      {
        persona: 'technical_lead',
        perspective: 'Technical perspective',
        reasoning: 'Technical reasoning',
        concerns: ['Performance'],
        requirements: ['High availability'],
      },
      {
        persona: 'business_analyst',
        perspective: 'Business perspective',
        reasoning: 'Business reasoning',
        concerns: ['Cost'],
        requirements: ['ROI'],
      },
    ],
  };

  const mockProps = {
    adr: mockADR,
    onClose: vi.fn(),
    onAnalyze: vi.fn(),
    isAnalyzing: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Mock scrollIntoView for all tests
    Element.prototype.scrollIntoView = vi.fn();
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

  describe('Bulk Refinement', () => {
    it('should show "Refine All Personas" button when personas exist', () => {
      render(<ADRModal {...mockProps} adr={mockADRWithPersonas} />);

      expect(screen.getByText('Refine All Personas')).toBeInTheDocument();
    });

    it('should not show "Refine All Personas" button when no personas exist', () => {
      render(<ADRModal {...mockProps} />);

      expect(screen.queryByText('Refine All Personas')).not.toBeInTheDocument();
    });

    it('should toggle bulk refinement section when button is clicked', async () => {
      const user = userEvent.setup();
      render(<ADRModal {...mockProps} adr={mockADRWithPersonas} />);

      const refineButton = screen.getByText('Refine All Personas');
      await user.click(refineButton);

      // Should show the bulk refinement section (text is split across elements)
      expect(screen.getByText(/This refinement prompt will be applied to all/)).toBeInTheDocument();
      expect(screen.getByText(/personas to regenerate their perspectives/)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/Enter refinement instructions/)).toBeInTheDocument();
      
      // Button text should change
      expect(screen.getByText('Hide Bulk Refine')).toBeInTheDocument();
    });

    it('should hide bulk refinement section when button is clicked again', async () => {
      const user = userEvent.setup();
      render(<ADRModal {...mockProps} adr={mockADRWithPersonas} />);

      const refineButton = screen.getByText('Refine All Personas');
      await user.click(refineButton);
      
      // Click again to hide
      const hideButton = screen.getByText('Hide Bulk Refine');
      await user.click(hideButton);

      // Should hide the section
      expect(screen.queryByText(/refinement prompt will be applied/)).not.toBeInTheDocument();
      expect(screen.queryByPlaceholderText(/Enter refinement instructions/)).not.toBeInTheDocument();
    });

    it('should update bulk refinement prompt when typing in textarea', async () => {
      const user = userEvent.setup();
      render(<ADRModal {...mockProps} adr={mockADRWithPersonas} />);

      const refineButton = screen.getByText('Refine All Personas');
      await user.click(refineButton);

      const textarea = screen.getByPlaceholderText(/Enter refinement instructions/);
      await user.type(textarea, 'Add more security considerations');

      expect(textarea).toHaveValue('Add more security considerations');
    });

    it('should disable submit button when prompt is empty', async () => {
      const user = userEvent.setup();
      render(<ADRModal {...mockProps} adr={mockADRWithPersonas} />);

      const refineButton = screen.getByText('Refine All Personas');
      await user.click(refineButton);

      const submitButton = screen.getByText('Submit Bulk Refinement');
      expect(submitButton).toBeDisabled();
    });

    it('should enable submit button when prompt has content', async () => {
      const user = userEvent.setup();
      render(<ADRModal {...mockProps} adr={mockADRWithPersonas} />);

      const refineButton = screen.getByText('Refine All Personas');
      await user.click(refineButton);

      const textarea = screen.getByPlaceholderText(/Enter refinement instructions/);
      await user.type(textarea, 'Test prompt');

      const submitButton = screen.getByText('Submit Bulk Refinement');
      expect(submitButton).not.toBeDisabled();
    });

    it('should call onRefineQueued with task id on successful submission', async () => {
      const { apiClient } = await import('@/lib/api');
      const mockRefinePersonas = vi.fn().mockResolvedValue({ task_id: 'task-123' });
      vi.mocked(apiClient).refinePersonas = mockRefinePersonas;

      const mockOnRefineQueued = vi.fn();
      const user = userEvent.setup();
      render(
        <ADRModal 
          {...mockProps} 
          adr={mockADRWithPersonas} 
          onRefineQueued={mockOnRefineQueued}
        />
      );

      const refineButton = screen.getByText('Refine All Personas');
      await user.click(refineButton);

      const textarea = screen.getByPlaceholderText(/Enter refinement instructions/);
      await user.type(textarea, 'Add security details');

      const submitButton = screen.getByText('Submit Bulk Refinement');
      await user.click(submitButton);

      // Should call API with all personas
      await vi.waitFor(() => {
        expect(mockRefinePersonas).toHaveBeenCalledWith(
          'adr-123',
          {
            refinements: [
              {
                persona: 'technical_lead',
                refinement_prompt: 'Add security details',
              },
              {
                persona: 'business_analyst',
                refinement_prompt: 'Add security details',
              },
            ],
            refinements_to_delete: undefined,
            provider_id: undefined,
          }
        );
      });

      // Should notify parent
      expect(mockOnRefineQueued).toHaveBeenCalledWith('task-123');
    });

    it('should close both modals after successful bulk refinement', async () => {
      const { apiClient } = await import('@/lib/api');
      const mockRefinePersonas = vi.fn().mockResolvedValue({ task_id: 'task-123' });
      vi.mocked(apiClient).refinePersonas = mockRefinePersonas;

      const mockOnClose = vi.fn();
      const user = userEvent.setup();
      render(
        <ADRModal 
          {...mockProps} 
          adr={mockADRWithPersonas} 
          onClose={mockOnClose}
        />
      );

      const refineButton = screen.getByText('Refine All Personas');
      await user.click(refineButton);

      const textarea = screen.getByPlaceholderText(/Enter refinement instructions/);
      await user.type(textarea, 'Test');

      const submitButton = screen.getByText('Submit Bulk Refinement');
      await user.click(submitButton);

      await vi.waitFor(() => {
        expect(mockOnClose).toHaveBeenCalled();
      });
    });

    it('should reset bulk refinement state after canceling', async () => {
      const user = userEvent.setup();
      render(<ADRModal {...mockProps} adr={mockADRWithPersonas} />);

      const refineButton = screen.getByText('Refine All Personas');
      await user.click(refineButton);

      const textarea = screen.getByPlaceholderText(/Enter refinement instructions/);
      await user.type(textarea, 'Some text');

      const cancelButton = screen.getByText('Cancel');
      await user.click(cancelButton);

      // Reopen the section
      const refineButtonAgain = screen.getByText('Refine All Personas');
      await user.click(refineButtonAgain);

      // Textarea should be empty
      const textareaAgain = screen.getByPlaceholderText(/Enter refinement instructions/);
      expect(textareaAgain).toHaveValue('');
    });

    it('should show error toast on bulk refinement failure', async () => {
      const { apiClient } = await import('@/lib/api');
      const mockRefinePersonas = vi.fn().mockRejectedValue(new Error('API Error'));
      vi.mocked(apiClient).refinePersonas = mockRefinePersonas;

      const user = userEvent.setup();
      render(<ADRModal {...mockProps} adr={mockADRWithPersonas} />);

      const refineButton = screen.getByText('Refine All Personas');
      await user.click(refineButton);

      const textarea = screen.getByPlaceholderText(/Enter refinement instructions/);
      await user.type(textarea, 'Test');

      const submitButton = screen.getByText('Submit Bulk Refinement');
      await user.click(submitButton);

      // Should show error toast
      await vi.waitFor(() => {
        expect(screen.getByText(/Failed to queue persona refinement/)).toBeInTheDocument();
      });
    });

    it('should not submit if prompt is only whitespace', async () => {
      const { apiClient } = await import('@/lib/api');
      const mockRefinePersonas = vi.fn();
      vi.mocked(apiClient).refinePersonas = mockRefinePersonas;

      const user = userEvent.setup();
      render(<ADRModal {...mockProps} adr={mockADRWithPersonas} />);

      const refineButton = screen.getByText('Refine All Personas');
      await user.click(refineButton);

      const textarea = screen.getByPlaceholderText(/Enter refinement instructions/);
      await user.type(textarea, '   '); // Only spaces

      const submitButton = screen.getByText('Submit Bulk Refinement');
      await user.click(submitButton);

      // Should not call API
      expect(mockRefinePersonas).not.toHaveBeenCalled();
    });
  });

  describe('Sticky Footer Layout', () => {
    it('should render modal with flex column layout', () => {
      render(<ADRModal {...mockProps} />);

      // Find the modal container (direct child of the backdrop)
      const backdrop = screen.getByRole('button', { name: 'Close' }).closest('.fixed');
      const modalContainer = backdrop?.querySelector('.max-w-4xl');

      expect(modalContainer).toHaveClass('flex', 'flex-col');
    });

    it('should have scrollable content area with flex-1', () => {
      render(<ADRModal {...mockProps} />);

      // The content area should have overflow-y-auto and flex-1
      const contentArea = screen.getByText('Context & Problem').closest('.overflow-y-auto');
      expect(contentArea).toHaveClass('flex-1', 'overflow-y-auto');
    });

    it('should have sticky footer with buttons', () => {
      render(<ADRModal {...mockProps} />);

      // Footer should contain the action buttons
      const closeButton = screen.getByRole('button', { name: 'Close' });
      const analyzeButton = screen.getByRole('button', { name: 'Analyze ADR' });
      const footer = closeButton.closest('.flex-shrink-0');

      expect(footer).toBeInTheDocument();
      expect(footer).toHaveClass('flex-shrink-0');
      expect(footer).toContainElement(closeButton);
      expect(footer).toContainElement(analyzeButton);
    });

    it('should show persona buttons in footer when personas exist', () => {
      render(<ADRModal {...mockProps} adr={mockADRWithPersonas} />);

      expect(screen.getByText(/Show Personas \(2\)/)).toBeInTheDocument();
      expect(screen.getByText('Refine All Personas')).toBeInTheDocument();
    });
  });

  describe('Scroll-to-View Behavior', () => {
    it('should scroll to bulk refinement section when opened', async () => {
      const user = userEvent.setup();
      render(<ADRModal {...mockProps} adr={mockADRWithPersonas} />);

      const refineButton = screen.getByText('Refine All Personas');
      await user.click(refineButton);

      // Should call scrollIntoView with smooth behavior
      await vi.waitFor(() => {
        expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
          behavior: 'smooth',
          block: 'nearest',
        });
      });
    });

    it('should not scroll when bulk refinement is closed', async () => {
      const user = userEvent.setup();
      render(<ADRModal {...mockProps} adr={mockADRWithPersonas} />);

      const refineButton = screen.getByText('Refine All Personas');
      await user.click(refineButton);

      vi.mocked(Element.prototype.scrollIntoView).mockClear();

      // Close the section
      const hideButton = screen.getByText('Hide Bulk Refine');
      await user.click(hideButton);

      // Should not scroll when closing
      expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled();
    });
  });
});
