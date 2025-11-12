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
    getQueueStatus: vi.fn(),
    getQueueTasks: vi.fn(),
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
    (apiClient.getQueueStatus as any).mockResolvedValue({ 
      total_tasks: 0, 
      active_tasks: 0, 
      pending_tasks: 0, 
      workers_online: 1 
    });
    (apiClient.getQueueTasks as any).mockResolvedValue([]);
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

describe('Home Page - Multi-Select Feature', () => {
  const mockADRs = {
    adrs: [
      {
        metadata: {
          id: 'adr-1',
          title: 'Test ADR 1',
          status: ADRStatus.PROPOSED,
          author: 'Test Author',
          created_at: '2025-01-01T00:00:00Z',
          updated_at: '2025-01-01T00:00:00Z',
          tags: ['test'],
          related_adrs: [],
          custom_fields: {},
        },
        content: {
          context_and_problem: 'Test context 1',
          decision_outcome: 'Test decision 1',
          consequences: 'Test consequences 1',
        },
      },
      {
        metadata: {
          id: 'adr-2',
          title: 'Test ADR 2',
          status: ADRStatus.ACCEPTED,
          author: 'Test Author 2',
          created_at: '2025-01-02T00:00:00Z',
          updated_at: '2025-01-02T00:00:00Z',
          tags: ['test'],
          related_adrs: [],
          custom_fields: {},
        },
        content: {
          context_and_problem: 'Test context 2',
          decision_outcome: 'Test decision 2',
          consequences: 'Test consequences 2',
        },
      },
    ],
    total: 2,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (apiClient.getADRs as any).mockResolvedValue(mockADRs);
    (apiClient.getADRRAGStatus as any).mockResolvedValue({ exists_in_rag: false });
    
    // Mock WebSocket hook
    vi.mock('@/hooks/useCacheStatusWebSocket', () => ({
      useCacheStatusWebSocket: () => ({
        isRebuilding: false,
        lastSyncTime: Date.now(),
        isConnected: true,
      }),
    }));
  });

  it('should show Select Mode button when ADRs exist', async () => {
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId('adr-card-adr-1')).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /select mode/i })).toBeInTheDocument();
  });

  it('should toggle into selection mode', async () => {
    const user = userEvent.setup();
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId('adr-card-adr-1')).toBeInTheDocument();
    });

    const selectModeButton = screen.getByRole('button', { name: /select mode/i });
    await user.click(selectModeButton);

    expect(screen.getByRole('button', { name: /exit select mode/i })).toBeInTheDocument();
    expect(screen.getByText(/0 of 2 selected/i)).toBeInTheDocument();
  });

  it('should show Select All and Unselect All buttons in selection mode', async () => {
    const user = userEvent.setup();
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId('adr-card-adr-1')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /select mode/i }));

    expect(screen.getByRole('button', { name: /^select all$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /unselect all/i })).toBeInTheDocument();
  });

  it('should show export and delete buttons in selection mode', async () => {
    const user = userEvent.setup();
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId('adr-card-adr-1')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /select mode/i }));

    expect(screen.getByRole('button', { name: /export selected/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /delete selected/i })).toBeInTheDocument();
  });

  it('should export selected ADRs with correct schema format', async () => {
    const user = userEvent.setup();
    
    // Track what was passed to createObjectURL
    let capturedBlob: Blob | null = null;
    const mockCreateObjectURL = vi.fn((blob: Blob) => {
      capturedBlob = blob;
      return 'blob:mock-url';
    });
    const mockRevokeObjectURL = vi.fn();
    global.URL.createObjectURL = mockCreateObjectURL;
    global.URL.revokeObjectURL = mockRevokeObjectURL;

    // Mock the anchor click without breaking createElement
    const originalClick = HTMLAnchorElement.prototype.click;
    const mockClick = vi.fn();
    HTMLAnchorElement.prototype.click = mockClick;

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId('adr-card-adr-1')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /select mode/i }));
    await user.click(screen.getByRole('button', { name: /^select all$/i }));
    await user.click(screen.getByRole('button', { name: /export selected/i }));

    await waitFor(() => {
      expect(mockCreateObjectURL).toHaveBeenCalled();
    });

    // Verify the blob content using FileReader
    expect(capturedBlob).toBeInstanceOf(Blob);
    
    // Read blob using FileReader (more compatible with test environment)
    const text = await new Promise<string>((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.readAsText(capturedBlob!);
    });
    
    const exportData = JSON.parse(text);

    // Verify schema format matches BulkADRExport (version 1.0.0)
    expect(exportData).toHaveProperty('schema');
    expect(exportData.schema).toMatchObject({
      schema_version: '1.0.0',
      total_records: 2,
    });
    expect(exportData.schema).toHaveProperty('exported_at');
    
    // Verify ADRs are in flattened format
    expect(exportData).toHaveProperty('adrs');
    expect(exportData.adrs).toHaveLength(2);
    expect(exportData.adrs[0]).toHaveProperty('id', 'adr-1');
    expect(exportData.adrs[0]).toHaveProperty('title', 'Test ADR 1');
    expect(exportData.adrs[0]).toHaveProperty('context_and_problem');
    
    // Verify download was triggered
    expect(mockClick).toHaveBeenCalled();
    
    // Cleanup
    HTMLAnchorElement.prototype.click = originalClick;
  });

  it('should delete selected ADRs when confirmed', async () => {
    const user = userEvent.setup();
    const mockConfirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    (apiClient.deleteADR as any).mockResolvedValue(undefined);

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId('adr-card-adr-1')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /select mode/i }));
    await user.click(screen.getByRole('button', { name: /^select all$/i }));
    await user.click(screen.getByRole('button', { name: /delete selected/i }));

    expect(mockConfirm).toHaveBeenCalledWith('Are you sure you want to delete 2 ADRs?');
    
    await waitFor(() => {
      expect(apiClient.deleteADR).toHaveBeenCalledWith('adr-1');
      expect(apiClient.deleteADR).toHaveBeenCalledWith('adr-2');
    });
  });

  it('should not delete if user cancels confirmation', async () => {
    const user = userEvent.setup();
    vi.spyOn(window, 'confirm').mockReturnValue(false);

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByTestId('adr-card-adr-1')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /select mode/i }));
    await user.click(screen.getByRole('button', { name: /^select all$/i }));
    await user.click(screen.getByRole('button', { name: /delete selected/i }));

    expect(apiClient.deleteADR).not.toHaveBeenCalled();
  });
});

