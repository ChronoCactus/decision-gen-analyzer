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

describe('ADRModal', () => {
  const mockADR: ADR = {
    metadata: {
      id: 'adr-123',
      title: 'Database Selection',
      status: ADRStatus.ACCEPTED,
      author: 'John Doe',
      created_date: '2024-01-15T10:00:00Z',
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
    const { rerender } = render(<ADRModal {...mockProps} />);

    let statusBadge = screen.getByText('accepted');
    expect(statusBadge).toHaveClass('bg-green-100', 'text-green-800');

    const proposedADR = { ...mockADR, metadata: { ...mockADR.metadata, status: ADRStatus.PROPOSED } };
    rerender(<ADRModal {...mockProps} adr={proposedADR} />);
    statusBadge = screen.getByText('proposed');
    expect(statusBadge).toHaveClass('bg-yellow-100', 'text-yellow-800');
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
});
