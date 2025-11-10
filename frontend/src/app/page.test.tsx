import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Home from './page';
import { ADRStatus } from '@/types/api';

// Mock components
vi.mock('@/components/ADRCard', () => ({
  ADRCard: ({ adr, onAnalyze, onDelete, onPushToRAG }: any) => (
    <div data-testid={`adr-card-${adr.metadata.id}`}>
      <div>{adr.metadata.title}</div>
      <button onClick={() => onAnalyze(adr.metadata.id)}>Analyze</button>
      <button onClick={() => onDelete(adr.metadata.id)}>Delete</button>
      <button onClick={() => onPushToRAG(adr.metadata.id)}>Push to RAG</button>
    </div>
  ),
}));

vi.mock('@/components/GenerateADRModal', () => ({
  GenerateADRModal: ({ onClose, onGenerate }: any) => (
    <div data-testid="generate-modal">
      <button onClick={() => onGenerate({ prompt: 'Test' })}>Submit</button>
      <button onClick={onClose}>Close</button>
    </div>
  ),
}));

// Mock apiClient
vi.mock('@/lib/api', () => ({
  apiClient: {
    getADRs: vi.fn(),
    analyzeADR: vi.fn(),
    deleteADR: vi.fn(),
    pushADRToRAG: vi.fn(),
    generateADR: vi.fn(),
    getAnalysisTaskStatus: vi.fn(),
    getGenerationTaskStatus: vi.fn(),
    getCacheStatus: vi.fn(),
    getADRRAGStatus: vi.fn(),
    exportADR: vi.fn(),
  },
}));

import { apiClient } from '@/lib/api';

describe('Home Page', () => {
  const mockADRs = {
    adrs: [
      {
        metadata: {
          id: 'adr-1',
          title: 'Database Selection',
          status: ADRStatus.ACCEPTED,
          author: 'John Doe',
          created_at: '2024-01-15',
          updated_at: '2024-01-15',
          tags: ['database'],
        },
        content: {
          context_and_problem: 'Need a database',
          decision_outcome: 'Use PostgreSQL',
          consequences: 'Good choice',
        },
      },
      {
        metadata: {
          id: 'adr-2',
          title: 'API Gateway',
          status: ADRStatus.PROPOSED,
          author: 'Jane Doe',
          created_at: '2024-01-16',
          updated_at: '2024-01-16',
          tags: ['api'],
        },
        content: {
          context_and_problem: 'Need an API gateway',
          decision_outcome: 'Use Kong',
          consequences: 'Flexible solution',
        },
      },
    ],
    total: 2,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (apiClient.getADRs as any).mockResolvedValue(mockADRs);
    (apiClient.getAnalysisTaskStatus as any).mockResolvedValue({ status: 'completed' });
    (apiClient.getGenerationTaskStatus as any).mockResolvedValue({ status: 'completed' });
    (apiClient.getCacheStatus as any).mockResolvedValue({ is_rebuilding: false });
    (apiClient.getADRRAGStatus as any).mockResolvedValue({ exists_in_rag: false });
  });

  it('should load and display ADRs on mount', async () => {
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId('adr-card-adr-1')).toBeInTheDocument();
      expect(screen.getByTestId('adr-card-adr-2')).toBeInTheDocument();
    });

    expect(screen.getByText('Database Selection')).toBeInTheDocument();
    expect(screen.getByText('API Gateway')).toBeInTheDocument();
  });

  it('should show loading state initially', () => {
    (apiClient.getADRs as any).mockImplementation(() => new Promise(() => {}));
    render(<Home />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('should handle load error', async () => {
    (apiClient.getADRs as any).mockRejectedValue(new Error('Failed to load'));
    
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to load/i)).toBeInTheDocument();
    });
  });

  it('should open generate modal when generate button is clicked', async () => {
    const user = userEvent.setup();
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId('adr-card-adr-1')).toBeInTheDocument();
    });

    const generateButton = screen.getByText(/Generate New ADR/i);
    await user.click(generateButton);

    expect(screen.getByTestId('generate-modal')).toBeInTheDocument();
  });

  it('should close generate modal', async () => {
    const user = userEvent.setup();
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId('adr-card-adr-1')).toBeInTheDocument();
    });

    const generateButton = screen.getByText(/Generate New ADR/i);
    await user.click(generateButton);
    
    const closeButton = screen.getByText('Close');
    await user.click(closeButton);

    expect(screen.queryByTestId('generate-modal')).not.toBeInTheDocument();
  });

  it('should handle ADR analysis', async () => {
    const user = userEvent.setup({ delay: null });
    (apiClient.analyzeADR as any).mockResolvedValue({
      task_id: 'task-123',
      status: 'queued',
      message: 'Analysis queued',
    });

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId('adr-card-adr-1')).toBeInTheDocument();
    });

    const analyzeButtons = screen.getAllByText('Analyze');
    await user.click(analyzeButtons[0]);

    await waitFor(() => {
      expect(apiClient.analyzeADR).toHaveBeenCalledWith({ adr_id: 'adr-1' });
    });
  });

  it('should handle ADR deletion', async () => {
    const user = userEvent.setup();
    (apiClient.deleteADR as any).mockResolvedValue({ message: 'Deleted' });

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId('adr-card-adr-1')).toBeInTheDocument();
    });

    // Mock getADRs to return updated list after deletion
    const updatedADRs = {
      adrs: [mockADRs.adrs[1]], // Only ADR-2 remains
      total: 1,
    };
    (apiClient.getADRs as any).mockResolvedValue(updatedADRs);

    const deleteButtons = screen.getAllByText('Delete');
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(apiClient.deleteADR).toHaveBeenCalledWith('adr-1');
    });

    // Verify the ADR is removed from the list
    await waitFor(() => {
      expect(screen.queryByTestId('adr-card-adr-1')).not.toBeInTheDocument();
    });
  });

  it('should handle push to RAG', async () => {
    const user = userEvent.setup();
    (apiClient.pushADRToRAG as any).mockResolvedValue({
      message: 'Success',
      adr_id: 'adr-1',
      title: 'Database Selection',
    });

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId('adr-card-adr-1')).toBeInTheDocument();
    });

    const ragButtons = screen.getAllByText('Push to RAG');
    await user.click(ragButtons[0]);

    await waitFor(() => {
      expect(apiClient.pushADRToRAG).toHaveBeenCalledWith('adr-1');
    });
    
    // Note: Success feedback is provided via WebSocket, not alert
  });

  it('should handle ADR generation', async () => {
    const user = userEvent.setup({ delay: null });
    (apiClient.generateADR as any).mockResolvedValue({
      task_id: 'task-456',
      status: 'queued',
      message: 'Generation queued',
    });

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId('adr-card-adr-1')).toBeInTheDocument();
    });

    // Open modal
    const generateButton = screen.getByText(/Generate New ADR/i);
    await user.click(generateButton);

    // Submit generation
    const submitButton = screen.getByText('Submit');
    await user.click(submitButton);

    await waitFor(() => {
      expect(apiClient.generateADR).toHaveBeenCalledWith({ prompt: 'Test' });
    });
  });

  it('should display task notifications', async () => {
    const user = userEvent.setup({ delay: null });
    (apiClient.analyzeADR as any).mockResolvedValue({
      task_id: 'task-123',
      status: 'queued',
      message: 'Analysis queued',
    });
    
    // Mock the status check to return in-progress state
    (apiClient.getAnalysisTaskStatus as any).mockResolvedValue({
      status: 'progress',
      message: 'Analyzing ADR...',
    });

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId('adr-card-adr-1')).toBeInTheDocument();
    });

    const analyzeButtons = screen.getAllByText('Analyze');
    await user.click(analyzeButtons[0]);

    // Wait for the task notification to appear (either initial or updated message)
    await waitFor(() => {
      const notification = screen.queryByText(/Analysis queued/i) || screen.queryByText(/Analyzing ADR/i);
      expect(notification).toBeInTheDocument();
    }, { timeout: 2000 });
  });
});
