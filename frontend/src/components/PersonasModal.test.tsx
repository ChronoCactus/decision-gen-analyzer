import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PersonasModal } from './PersonasModal';
import { PersonaResponse } from '@/types/api';

// Mock the useEscapeKey hook
vi.mock('@/hooks/useEscapeKey', () => ({
  useEscapeKey: vi.fn(),
}));

describe('PersonasModal', () => {
  const mockPersonas: PersonaResponse[] = [
    {
      persona: 'technical_lead',
      perspective: 'Technical perspective on the decision',
      recommended_option: 'Option A',
      reasoning: 'This is the best technical choice',
      concerns: ['Performance', 'Scalability'],
      requirements: ['High availability', 'Low latency'],
    },
    {
      persona: 'business_analyst',
      perspective: 'Business perspective on the decision',
      reasoning: 'This aligns with business goals',
      concerns: ['Cost', 'ROI'],
      requirements: ['Budget approval', 'Stakeholder buy-in'],
    },
  ];

  const mockProps = {
    personas: mockPersonas,
    adrId: 'test-adr-id',
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Mock scrollIntoView for all tests
    Element.prototype.scrollIntoView = vi.fn();
  });

  it('should render personas modal with title', () => {
    render(<PersonasModal {...mockProps} />);

    expect(screen.getByText('Individual Persona Responses')).toBeInTheDocument();
  });

  it('should display all personas', () => {
    render(<PersonasModal {...mockProps} />);

    expect(screen.getByText('Technical Lead')).toBeInTheDocument();
    expect(screen.getByText('Business Analyst')).toBeInTheDocument();
  });

  it('should show persona perspectives', () => {
    render(<PersonasModal {...mockProps} />);

    expect(screen.getByText('Technical perspective on the decision')).toBeInTheDocument();
    expect(screen.getByText('Business perspective on the decision')).toBeInTheDocument();
  });

  it('should show persona reasoning', () => {
    render(<PersonasModal {...mockProps} />);

    expect(screen.getByText('This is the best technical choice')).toBeInTheDocument();
    expect(screen.getByText('This aligns with business goals')).toBeInTheDocument();
  });

  it('should display recommended option when present', () => {
    render(<PersonasModal {...mockProps} />);

    expect(screen.getByText('Recommends: Option A')).toBeInTheDocument();
  });

  it('should not display recommended option when not present', () => {
    render(<PersonasModal {...mockProps} />);

    // business_analyst doesn't have recommended_option
    const businessAnalystSection = screen.getByText('Business Analyst').closest('div');
    expect(businessAnalystSection).not.toHaveTextContent('Recommends:');
  });

  it('should display concerns', () => {
    render(<PersonasModal {...mockProps} />);

    expect(screen.getByText('Performance')).toBeInTheDocument();
    expect(screen.getByText('Scalability')).toBeInTheDocument();
    expect(screen.getByText('Cost')).toBeInTheDocument();
    expect(screen.getByText('ROI')).toBeInTheDocument();
  });

  it('should display requirements', () => {
    render(<PersonasModal {...mockProps} />);

    expect(screen.getByText('High availability')).toBeInTheDocument();
    expect(screen.getByText('Low latency')).toBeInTheDocument();
    expect(screen.getByText('Budget approval')).toBeInTheDocument();
    expect(screen.getByText('Stakeholder buy-in')).toBeInTheDocument();
  });

  it('should call onClose when close button is clicked', async () => {
    const user = userEvent.setup();
    render(<PersonasModal {...mockProps} />);

    // Get the close button in the header (first button) or by text
    const closeButton = screen.getByText('Close');
    await user.click(closeButton);

    expect(mockProps.onClose).toHaveBeenCalledTimes(1);
  });

  it('should format persona names correctly', () => {
    const personaWithUnderscore: PersonaResponse = {
      persona: 'security_expert',
      perspective: 'Security perspective',
      reasoning: 'Security is important',
      concerns: [],
      requirements: [],
    };

    render(<PersonasModal {...mockProps} personas={[personaWithUnderscore]} />);

    expect(screen.getByText('Security Expert')).toBeInTheDocument();
  });

  it('should render persona emoji icons', () => {
    render(<PersonasModal {...mockProps} />);

    // Check that emoji containers exist (jsdom doesn't render emojis perfectly)
    const avatarDivs = document.querySelectorAll('.bg-blue-100.rounded-full');
    expect(avatarDivs.length).toBe(2); // One for each persona
    
    // Check that each contains a span with emoji (even if jsdom doesn't render the exact character)
    avatarDivs.forEach(div => {
      const emojiSpan = div.querySelector('span.text-2xl');
      expect(emojiSpan).toBeInTheDocument();
    });
  });

  it('should handle empty personas array', () => {
    render(<PersonasModal {...mockProps} personas={[]} />);

    expect(screen.getByText('Individual Persona Responses')).toBeInTheDocument();
    // No persona names should be displayed
    expect(screen.queryByText('Technical Lead')).not.toBeInTheDocument();
  });

  describe('Refinement History', () => {
    const personaWithHistory: PersonaResponse = {
      persona: 'technical_lead',
      perspective: 'Technical perspective',
      reasoning: 'Technical reasoning',
      concerns: [],
      requirements: [],
      refinement_history: [
        'First refinement prompt',
        'Second refinement prompt',
        'Third refinement prompt',
      ],
    };

    it('should display refinement history when present', () => {
      render(<PersonasModal {...mockProps} personas={[personaWithHistory]} />);

      expect(screen.getByText('Refinement History (3)')).toBeInTheDocument();
      expect(screen.getByText('Refinement #1')).toBeInTheDocument();
      expect(screen.getByText('First refinement prompt')).toBeInTheDocument();
      expect(screen.getByText('Refinement #2')).toBeInTheDocument();
      expect(screen.getByText('Second refinement prompt')).toBeInTheDocument();
      expect(screen.getByText('Refinement #3')).toBeInTheDocument();
      expect(screen.getByText('Third refinement prompt')).toBeInTheDocument();
    });

    it('should not display refinement history section when empty', () => {
      const personaWithoutHistory = { ...personaWithHistory, refinement_history: [] };
      render(<PersonasModal {...mockProps} personas={[personaWithoutHistory]} />);

      expect(screen.queryByText(/Refinement History/)).not.toBeInTheDocument();
    });

    it('should show delete button for each refinement', () => {
      render(<PersonasModal {...mockProps} personas={[personaWithHistory]} />);

      const deleteButtons = screen.getAllByText('Delete');
      expect(deleteButtons).toHaveLength(3);
    });

    it('should mark refinement for deletion when delete button is clicked', async () => {
      const user = userEvent.setup();
      render(<PersonasModal {...mockProps} personas={[personaWithHistory]} />);

      const deleteButtons = screen.getAllByText('Delete');
      await user.click(deleteButtons[0]);

      // Should now show "Undo" instead of "Delete"
      expect(screen.getByText('Undo')).toBeInTheDocument();
      // Should show pending deletion text
      expect(screen.getByText('Refinement #1 (Pending Deletion)')).toBeInTheDocument();
      // Should apply strikethrough styling (check the outer refinement card for opacity-50)
      const refinementText = screen.getByText('Refinement #1 (Pending Deletion)');
      const outerCard = refinementText.parentElement?.parentElement;
      expect(outerCard).toHaveClass('opacity-50');
    });

    it('should unmark refinement when undo button is clicked', async () => {
      const user = userEvent.setup();
      render(<PersonasModal {...mockProps} personas={[personaWithHistory]} />);

      const deleteButtons = screen.getAllByText('Delete');
      await user.click(deleteButtons[0]);

      // Now click undo
      const undoButton = screen.getByText('Undo');
      await user.click(undoButton);

      // Should revert back to "Delete" button
      expect(screen.getAllByText('Delete')).toHaveLength(3);
      expect(screen.queryByText('Undo')).not.toBeInTheDocument();
      expect(screen.queryByText('(Pending Deletion)')).not.toBeInTheDocument();
    });

    it('should allow marking multiple refinements for deletion', async () => {
      const user = userEvent.setup();
      render(<PersonasModal {...mockProps} personas={[personaWithHistory]} />);

      const deleteButtons = screen.getAllByText('Delete');
      await user.click(deleteButtons[0]);
      await user.click(deleteButtons[2]); // Click third one (index 2 in original array)

      // Should have 2 undo buttons
      expect(screen.getAllByText('Undo')).toHaveLength(2);
      // Should have 1 delete button remaining
      expect(screen.getAllByText('Delete')).toHaveLength(1);
      expect(screen.getByText('Refinement #1 (Pending Deletion)')).toBeInTheDocument();
      expect(screen.getByText('Refinement #3 (Pending Deletion)')).toBeInTheDocument();
    });
  });

  describe('Refinement Functionality', () => {
    it('should show refine button for each persona', () => {
      render(<PersonasModal {...mockProps} />);

      const refineButtons = screen.getAllByText('Refine');
      expect(refineButtons).toHaveLength(2); // One for each persona
    });

    it('should toggle refinement textarea when refine button is clicked', async () => {
      const user = userEvent.setup();
      render(<PersonasModal {...mockProps} />);

      const refineButtons = screen.getAllByText('Refine');
      await user.click(refineButtons[0]);

      // Should show textarea
      expect(screen.getByPlaceholderText(/Enter additional instructions/)).toBeInTheDocument();
      expect(screen.getByText('Refinement Prompt')).toBeInTheDocument();
    });

    it('should hide refinement textarea when cancel button is clicked', async () => {
      const user = userEvent.setup();
      render(<PersonasModal {...mockProps} />);

      const refineButtons = screen.getAllByText('Refine');
      await user.click(refineButtons[0]);

      // Should show textarea
      expect(screen.getByPlaceholderText(/Enter additional instructions/)).toBeInTheDocument();

      // Click cancel (now showing as "Cancel" instead of "Refine")
      const cancelButton = screen.getByText('Cancel');
      await user.click(cancelButton);

      // Textarea should be hidden
      expect(screen.queryByPlaceholderText(/Enter additional instructions/)).not.toBeInTheDocument();
    });

    it('should update refinement prompt when typing in textarea', async () => {
      const user = userEvent.setup();
      render(<PersonasModal {...mockProps} />);

      const refineButtons = screen.getAllByText('Refine');
      await user.click(refineButtons[0]);

      const textarea = screen.getByPlaceholderText(/Enter additional instructions/);
      await user.type(textarea, 'Add more security details');

      expect(textarea).toHaveValue('Add more security details');
    });

    it('should show submit button when there are refinement changes', async () => {
      const user = userEvent.setup();
      const mockOnRefine = vi.fn();
      render(<PersonasModal {...mockProps} onRefine={mockOnRefine} />);

      const refineButtons = screen.getAllByText('Refine');
      await user.click(refineButtons[0]);

      const textarea = screen.getByPlaceholderText(/Enter additional instructions/);
      await user.type(textarea, 'Add security');

      // Submit button should appear
      expect(screen.getByText(/Submit Changes/)).toBeInTheDocument();
    });

    it('should call onRefine with correct data when submitting new refinements', async () => {
      const user = userEvent.setup();
      const mockOnRefine = vi.fn();
      render(<PersonasModal {...mockProps} onRefine={mockOnRefine} />);

      const refineButtons = screen.getAllByText('Refine');
      await user.click(refineButtons[0]);

      const textarea = screen.getByPlaceholderText(/Enter additional instructions/);
      await user.type(textarea, 'Add security details');

      const submitButton = screen.getByText(/Submit Changes/);
      await user.click(submitButton);

      expect(mockOnRefine).toHaveBeenCalledWith(
        [
          {
            persona: 'technical_lead',
            refinement_prompt: 'Add security details',
          },
        ],
        {}
      );
    });

    it('should call onRefine with deletions when submitting only deletions', async () => {
      const user = userEvent.setup();
      const mockOnRefine = vi.fn();
      const personaWithHistory: PersonaResponse = {
        persona: 'technical_lead',
        perspective: 'Technical perspective',
        reasoning: 'Technical reasoning',
        concerns: [],
        requirements: [],
        refinement_history: ['First refinement', 'Second refinement'],
      };

      render(<PersonasModal {...mockProps} personas={[personaWithHistory]} onRefine={mockOnRefine} />);

      // Mark first refinement for deletion
      const deleteButtons = screen.getAllByText('Delete');
      await user.click(deleteButtons[0]);

      const submitButton = screen.getByText(/Submit Changes/);
      await user.click(submitButton);

      expect(mockOnRefine).toHaveBeenCalledWith(
        [],
        { technical_lead: [0] }
      );
    });

    it('should call onRefine with both refinements and deletions', async () => {
      const user = userEvent.setup();
      const mockOnRefine = vi.fn();
      const personaWithHistory: PersonaResponse = {
        persona: 'technical_lead',
        perspective: 'Technical perspective',
        reasoning: 'Technical reasoning',
        concerns: [],
        requirements: [],
        refinement_history: ['Old refinement'],
      };

      render(<PersonasModal {...mockProps} personas={[personaWithHistory]} onRefine={mockOnRefine} />);

      // Mark refinement for deletion
      const deleteButton = screen.getByText('Delete');
      await user.click(deleteButton);

      // Add new refinement
      const refineButton = screen.getByText('Refine');
      await user.click(refineButton);

      const textarea = screen.getByPlaceholderText(/Enter additional instructions/);
      await user.type(textarea, 'New refinement');

      const submitButton = screen.getByText(/Submit Changes/);
      await user.click(submitButton);

      expect(mockOnRefine).toHaveBeenCalledWith(
        [
          {
            persona: 'technical_lead',
            refinement_prompt: 'New refinement',
          },
        ],
        { technical_lead: [0] }
      );
    });

    it('should reset state after successful submission', async () => {
      const user = userEvent.setup();
      const mockOnRefine = vi.fn().mockResolvedValue(undefined);
      render(<PersonasModal {...mockProps} onRefine={mockOnRefine} />);

      const refineButtons = screen.getAllByText('Refine');
      await user.click(refineButtons[0]);

      const textarea = screen.getByPlaceholderText(/Enter additional instructions/);
      await user.type(textarea, 'Test refinement');

      const submitButton = screen.getByText(/Submit Changes/);
      await user.click(submitButton);

      // Wait for async operations
      await vi.waitFor(() => {
        expect(mockOnRefine).toHaveBeenCalled();
      });

      // Submit button should be hidden (no changes)
      expect(screen.queryByText(/Submit Changes/)).not.toBeInTheDocument();
    });

    it('should show correct count in submit button', async () => {
      const user = userEvent.setup();
      const mockOnRefine = vi.fn();
      const personaWithHistory: PersonaResponse = {
        persona: 'technical_lead',
        perspective: 'Technical perspective',
        reasoning: 'Technical reasoning',
        concerns: [],
        requirements: [],
        refinement_history: ['Old refinement 1', 'Old refinement 2'],
      };

      render(<PersonasModal {...mockProps} personas={[personaWithHistory]} onRefine={mockOnRefine} />);

      // Mark 2 refinements for deletion
      const deleteButtons = screen.getAllByText('Delete');
      await user.click(deleteButtons[0]);
      await user.click(deleteButtons[1]);

      // Add 1 new refinement
      const refineButton = screen.getByText('Refine');
      await user.click(refineButton);
      const textarea = screen.getByPlaceholderText(/Enter additional instructions/);
      await user.type(textarea, 'New');

      // Should show count of 2 (counts personas, not individual refinements: 1 persona with prompt + 1 persona with deletions)
      expect(screen.getByText('Submit Changes (2)')).toBeInTheDocument();
    });
  });

  describe('Sticky Footer Layout', () => {
    it('should render modal with flex column layout', () => {
      render(<PersonasModal {...mockProps} />);

      // Find the modal container
      const backdrop = screen.getByText('Individual Persona Responses').closest('.fixed');
      // The container now has sm:max-w-4xl instead of max-w-4xl
      const modalContainer = backdrop?.querySelector('.w-full.h-full');

      expect(modalContainer).toHaveClass('flex', 'flex-col');
    });

    it('should have scrollable content area with flex-1', () => {
      render(<PersonasModal {...mockProps} />);

      // The content area should have overflow-y-auto and flex-1
      const contentArea = screen.getByText('Technical Lead').closest('.overflow-y-auto');
      expect(contentArea).toHaveClass('flex-1', 'overflow-y-auto');
    });

    it('should have sticky footer with close button', () => {
      render(<PersonasModal {...mockProps} />);

      // Footer should contain the close button (the one with text "Close", not the icon)
      const closeButton = screen.getByText('Close', { selector: 'button' });
      const footer = closeButton.closest('.flex-shrink-0');

      expect(footer).toBeInTheDocument();
      expect(footer).toHaveClass('flex-shrink-0');
      expect(footer).toContainElement(closeButton);
    });

    it('should show submit button in footer when there are changes', async () => {
      const user = userEvent.setup();
      render(<PersonasModal {...mockProps} onRefine={vi.fn()} />);

      const refineButtons = screen.getAllByText('Refine');
      await user.click(refineButtons[0]);

      const textarea = screen.getByPlaceholderText(/Enter additional instructions/);
      await user.type(textarea, 'Test');

      expect(screen.getByText(/Submit Changes/)).toBeInTheDocument();
    });
  });

  describe('Scroll-to-View Behavior', () => {
    it('should scroll to refinement section when refine is clicked', async () => {
      const user = userEvent.setup();
      render(<PersonasModal {...mockProps} onRefine={vi.fn()} />);

      const refineButtons = screen.getAllByText('Refine');
      await user.click(refineButtons[0]);

      // Should call scrollIntoView with smooth behavior
      await vi.waitFor(() => {
        expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
          behavior: 'smooth',
          block: 'nearest',
        });
      });
    });

    it('should scroll to correct persona when multiple refines are toggled', async () => {
      const user = userEvent.setup();
      render(<PersonasModal {...mockProps} onRefine={vi.fn()} />);

      const refineButtons = screen.getAllByText('Refine');

      // Toggle first persona
      await user.click(refineButtons[0]);
      await vi.waitFor(() => expect(Element.prototype.scrollIntoView).toHaveBeenCalled());

      vi.mocked(Element.prototype.scrollIntoView).mockClear();

      // Toggle second persona
      await user.click(refineButtons[1]);
      await vi.waitFor(() => expect(Element.prototype.scrollIntoView).toHaveBeenCalled());

      // Should have been called for both personas
      expect(Element.prototype.scrollIntoView).toHaveBeenCalledTimes(1);
    });

    it('should not scroll when refinement is cancelled', async () => {
      const user = userEvent.setup();
      render(<PersonasModal {...mockProps} onRefine={vi.fn()} />);

      const refineButton = screen.getAllByText('Refine')[0];
      await user.click(refineButton);

      await vi.waitFor(() => expect(Element.prototype.scrollIntoView).toHaveBeenCalled());
      vi.mocked(Element.prototype.scrollIntoView).mockClear();

      // Cancel refinement
      const cancelButton = screen.getByText('Cancel');
      await user.click(cancelButton);

      // Should not scroll when cancelling
      expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled();
    });
  });
});
