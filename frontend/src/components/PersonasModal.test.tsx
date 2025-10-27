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
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
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
});
