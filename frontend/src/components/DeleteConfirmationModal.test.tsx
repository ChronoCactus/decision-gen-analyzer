import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DeleteConfirmationModal } from './DeleteConfirmationModal';

// Mock the useEscapeKey hook
vi.mock('@/hooks/useEscapeKey', () => ({
  useEscapeKey: vi.fn(),
}));

describe('DeleteConfirmationModal', () => {
  const mockProps = {
    adrTitle: 'Test ADR Title',
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
    isDeleting: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render modal with ADR title', () => {
    render(<DeleteConfirmationModal {...mockProps} />);

    // "Delete ADR" appears in both heading and button
    expect(screen.getAllByText('Delete ADR').length).toBeGreaterThan(0);
    expect(screen.getByText('"Test ADR Title"')).toBeInTheDocument();
    expect(screen.getByText(/Are you sure you want to delete this ADR/)).toBeInTheDocument();
  });

  it('should display warning message', () => {
    render(<DeleteConfirmationModal {...mockProps} />);

    expect(screen.getByText(/This action will delete the ADR from local storage/)).toBeInTheDocument();
    expect(screen.getByText(/This action cannot be undone/)).toBeInTheDocument();
  });

  it('should call onCancel when Cancel button is clicked', async () => {
    const user = userEvent.setup();
    render(<DeleteConfirmationModal {...mockProps} />);

    await user.click(screen.getByText('Cancel'));

    expect(mockProps.onCancel).toHaveBeenCalledTimes(1);
    expect(mockProps.onConfirm).not.toHaveBeenCalled();
  });

  it('should call onConfirm when Delete ADR button is clicked', async () => {
    const user = userEvent.setup();
    render(<DeleteConfirmationModal {...mockProps} />);

    // Get the delete button by role to avoid ambiguity
    const buttons = screen.getAllByRole('button');
    const deleteButton = buttons.find(btn => btn.textContent === 'Delete ADR');
    await user.click(deleteButton!);

    expect(mockProps.onConfirm).toHaveBeenCalledTimes(1);
    expect(mockProps.onCancel).not.toHaveBeenCalled();
  });

  it('should show deleting state when isDeleting is true', () => {
    render(<DeleteConfirmationModal {...mockProps} isDeleting={true} />);

    expect(screen.getByText('Deleting...')).toBeInTheDocument();
    // "Delete ADR" still appears in the heading even when deleting
    const deleteButton = screen.queryByRole('button', { name: /Delete ADR/i });
    expect(deleteButton).not.toBeInTheDocument(); // Button text changes to "Deleting..."
  });

  it('should disable buttons when isDeleting is true', () => {
    render(<DeleteConfirmationModal {...mockProps} isDeleting={true} />);

    const cancelButton = screen.getByText('Cancel');
    const deleteButton = screen.getByText('Deleting...');

    expect(cancelButton).toBeDisabled();
    expect(deleteButton).toBeDisabled();
  });

  it('should enable buttons when isDeleting is false', () => {
    render(<DeleteConfirmationModal {...mockProps} isDeleting={false} />);

    const cancelButton = screen.getByText('Cancel');
    const buttons = screen.getAllByRole('button');
    const deleteButton = buttons.find(btn => btn.textContent === 'Delete ADR');

    expect(cancelButton).not.toBeDisabled();
    expect(deleteButton).not.toBeDisabled();
  });

  it('should have proper styling classes', () => {
    const { container } = render(<DeleteConfirmationModal {...mockProps} />);

    // Check for modal overlay
    const overlay = container.querySelector('.fixed.inset-0.bg-black.bg-opacity-50');
    expect(overlay).toBeInTheDocument();

    // Check for modal content
    const modal = container.querySelector('.bg-white.rounded-lg.shadow-xl');
    expect(modal).toBeInTheDocument();
  });

  it('should render warning icon', () => {
    const { container } = render(<DeleteConfirmationModal {...mockProps} />);

    const icon = container.querySelector('svg');
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveClass('text-red-600');
  });
});
