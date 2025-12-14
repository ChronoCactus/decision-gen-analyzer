import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { GenerateADRModal } from './GenerateADRModal';

// Mock apiClient
vi.mock('@/lib/api', () => ({
  apiClient: {
    getPersonas: vi.fn(),
    listProviders: vi.fn(),
    listMcpServers: vi.fn(),
  },
}));

// Mock the useEscapeKey hook
vi.mock('@/hooks/useEscapeKey', () => ({
  useEscapeKey: vi.fn(),
}));

import { apiClient } from '@/lib/api';

describe('GenerateADRModal', () => {
  const mockPersonas = {
    personas: [
      { value: 'technical_lead', label: 'Technical Lead', description: 'Tech focus' },
      { value: 'architect', label: 'Architect', description: 'Architecture focus' },
      { value: 'business_analyst', label: 'Business Analyst', description: 'Business focus' },
    ],
  };

  const mockProviders = {
    providers: [
      {
        id: 'provider-1',
        name: 'Default Provider',
        provider_type: 'ollama',
        model_name: 'gpt-oss:20b',
        base_url: 'http://localhost:11434/v1',
        is_default: true,
        temperature: 0.7,
      },
      {
        id: 'provider-2',
        name: 'Secondary Provider',
        provider_type: 'openai',
        model_name: 'gpt-4',
        base_url: 'https://api.openai.com/v1',
        is_default: false,
        temperature: 0.5,
      },
    ],
  };

  const mockProps = {
    onClose: vi.fn(),
    onGenerate: vi.fn(),
    isGenerating: false,
    generationStartTime: undefined,
  };

  const mockMcpServers = {
    servers: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (apiClient.getPersonas as any).mockResolvedValue(mockPersonas);
    (apiClient.listProviders as any).mockResolvedValue(mockProviders);
    (apiClient.listMcpServers as any).mockResolvedValue(mockMcpServers);
  });

  it('should render modal with form fields', async () => {
    const user = userEvent.setup();
    render(<GenerateADRModal {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText('Generate New ADR')).toBeInTheDocument();
    });

    expect(screen.getByPlaceholderText(/Describe the decision/)).toBeInTheDocument();
    
    // Context is initially hidden
    expect(screen.queryByPlaceholderText(/Any additional context/)).not.toBeInTheDocument();
    
    // Click to expand context
    const contextButton = screen.getByText(/Additional Context/);
    await user.click(contextButton);
    
    expect(screen.getByPlaceholderText(/Any additional context/)).toBeInTheDocument();
  });

  it('should load personas on mount', async () => {
    render(<GenerateADRModal {...mockProps} />);

    await waitFor(() => {
      expect(apiClient.getPersonas).toHaveBeenCalled();
      expect(apiClient.listProviders).toHaveBeenCalled();
    });
  });

  it('should render provider dropdown with available providers', async () => {
    render(<GenerateADRModal {...mockProps} />);

    await waitFor(() => {
      const providerSelect = screen.getByLabelText(/Synthesis Model/i);
      expect(providerSelect).toBeInTheDocument();
    });

    // Check that the default provider is selected
    const providerSelect = screen.getByLabelText(/Synthesis Model/i) as HTMLSelectElement;
    expect(providerSelect.value).toBe('provider-1');
  });

  it('should handle prompt input', async () => {
    const user = userEvent.setup();
    render(<GenerateADRModal {...mockProps} />);

    const promptInput = screen.getByPlaceholderText(/Describe the decision/);
    await user.type(promptInput, 'Test decision');

    expect(promptInput).toHaveValue('Test decision');
  });

  it('should handle context input', async () => {
    const user = userEvent.setup();
    render(<GenerateADRModal {...mockProps} />);

    // Expand context section
    const contextButton = screen.getByText(/Additional Context/);
    await user.click(contextButton);

    const contextInput = screen.getByPlaceholderText(/Any additional context/);
    await user.type(contextInput, 'Test context');

    await waitFor(() => {
      expect(contextInput).toHaveValue('Test context');
    });
  });

  it('should call onClose when cancel is clicked', async () => {
    const user = userEvent.setup();
    render(<GenerateADRModal {...mockProps} />);

    const cancelButton = screen.getByText('Cancel');
    await user.click(cancelButton);

    expect(mockProps.onClose).toHaveBeenCalledTimes(1);
  });

  it('should call onGenerate when form is submitted', async () => {
    const user = userEvent.setup();
    render(<GenerateADRModal {...mockProps} />);

    // Wait for personas and providers to load
    await waitFor(() => {
      expect(apiClient.getPersonas).toHaveBeenCalled();
      expect(apiClient.listProviders).toHaveBeenCalled();
    });

    const promptInput = screen.getByPlaceholderText(/Describe the decision/);
    await user.type(promptInput, 'Test decision');

    const generateButton = screen.getByText('Generate');
    await user.click(generateButton);

    expect(mockProps.onGenerate).toHaveBeenCalledWith(
      expect.objectContaining({
        prompt: 'Test decision',
        synthesis_provider_id: 'provider-1', // Default provider should be selected
      })
    );
  });

  it('should disable buttons when isGenerating is true', async () => {
    render(<GenerateADRModal {...mockProps} isGenerating={true} />);

    await waitFor(() => {
      // Get button by its role, filtered by the text it contains
      const buttons = screen.getAllByRole('button');
      const generateButton = buttons.find(btn => btn.textContent?.includes('Generating'));
      expect(generateButton).toBeDisabled();
      
      const cancelButton = screen.getByText('Cancel');
      expect(cancelButton).toBeDisabled();
    });
  });

  it('should show elapsed time when generating', async () => {
    vi.useFakeTimers();
    const startTime = Date.now();
    
    render(<GenerateADRModal {...mockProps} isGenerating={true} generationStartTime={startTime} />);

    // Wait for component to mount and start interval
    await vi.advanceTimersByTimeAsync(1000);

    // Advance time by 5 more seconds
    await vi.advanceTimersByTimeAsync(4000);

    // Check for elapsed time display
    expect(screen.getByText(/\(5s\)/)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it('should not submit form with empty prompt', async () => {
    const user = userEvent.setup({ delay: null });
    render(<GenerateADRModal {...mockProps} />);

    // Wait briefly for component to stabilize
    await waitFor(() => {
      expect(screen.getByText('Generate')).toBeInTheDocument();
    });

    // Try to click generate button (with empty prompt)
    const generateButton = screen.getByText('Generate');
    await user.click(generateButton);

    // onGenerate should not be called because prompt is empty (form validation prevents it)
    expect(mockProps.onGenerate).not.toHaveBeenCalled();
  });

  it('should handle persona loading error gracefully', async () => {
    // Suppress console.error for this test
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    
    (apiClient.getPersonas as any).mockRejectedValue(new Error('Failed to load'));
    (apiClient.listProviders as any).mockResolvedValue(mockProviders); // Providers still load
    
    render(<GenerateADRModal {...mockProps} />);

    // Modal title should render immediately regardless of persona loading
    expect(screen.getByText('Generate New ADR')).toBeInTheDocument();
    
    // Wait briefly for the personas call to complete (with rejection)
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Modal should still be functional
    expect(screen.getByPlaceholderText(/Describe the decision/)).toBeInTheDocument();
    
    consoleErrorSpy.mockRestore();
  });
});
