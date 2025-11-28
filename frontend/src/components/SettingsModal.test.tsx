import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SettingsModal } from './SettingsModal';
import { apiClient } from '@/lib/api';

// Mock dependencies
vi.mock('@/hooks/useEscapeKey', () => ({
  useEscapeKey: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  apiClient: {
    listProviders: vi.fn(),
    createProvider: vi.fn(),
    updateProvider: vi.fn(),
    deleteProvider: vi.fn(),
  },
}));

describe('SettingsModal', () => {
  const mockProviders = [
    {
      id: '1',
      name: 'Ollama Local',
      provider_type: 'ollama',
      base_url: 'http://localhost:11434',
      model_name: 'llama3',
      temperature: 0.7,
      is_default: true,
      is_env_based: false,
      has_api_key: false,
    }
  ];

  const mockInterfaceSettings = {
    autoDismissToasts: false,
    toastDismissTimeout: 5,
  };
  const mockUpdateInterfaceSettings = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (apiClient.listProviders as any).mockResolvedValue({ providers: mockProviders });
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders providers list', async () => {
    render(
      <SettingsModal
        onClose={() => { }}
        interfaceSettings={mockInterfaceSettings}
        onUpdateInterfaceSettings={mockUpdateInterfaceSettings}
      />
    );
    
    await waitFor(() => {
      expect(screen.getByText('Ollama Local')).toBeInTheDocument();
    });
  });

  it('validates OpenAI provider with Ollama endpoint', async () => {
    const user = userEvent.setup();
    render(
      <SettingsModal
        onClose={() => { }}
        interfaceSettings={mockInterfaceSettings}
        onUpdateInterfaceSettings={mockUpdateInterfaceSettings}
      />
    );
    
    await waitFor(() => {
      expect(screen.getByText('Ollama Local')).toBeInTheDocument();
    });

    // Click Add Provider
    await user.click(screen.getByText('+ Add Provider'));

    // Select OpenAI
    const typeSelect = screen.getByLabelText(/Provider Type/i);
    await user.selectOptions(typeSelect, 'openai');

    // Mock fetch to return success for /api/ps
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });

    // Enter Ollama URL
    const urlInput = screen.getByLabelText(/Base URL/i);
    await user.type(urlInput, 'http://localhost:11434');
    fireEvent.blur(urlInput);

    await waitFor(() => {
      expect(screen.getByText(/appears to be an Ollama server/i)).toBeInTheDocument();
    });
  });

  it('validates Llama.cpp provider without /v1', async () => {
    const user = userEvent.setup();
    render(
      <SettingsModal
        onClose={() => { }}
        interfaceSettings={mockInterfaceSettings}
        onUpdateInterfaceSettings={mockUpdateInterfaceSettings}
      />
    );
    
    await waitFor(() => {
      expect(screen.getByText('Ollama Local')).toBeInTheDocument();
    });

    // Click Add Provider
    await user.click(screen.getByText('+ Add Provider'));

    // Select llama.cpp
    const typeSelect = screen.getByLabelText(/Provider Type/i);
    await user.selectOptions(typeSelect, 'llama_cpp');

    // Enter URL without /v1
    const urlInput = screen.getByLabelText(/Base URL/i);
    await user.type(urlInput, 'http://localhost:8080');
    fireEvent.blur(urlInput);

    await waitFor(() => {
      expect(screen.getByText(/usually require '\/v1'/i)).toBeInTheDocument();
    });
  });

  it('handles parallel request settings', async () => {
    const user = userEvent.setup();
    render(
      <SettingsModal
        onClose={() => { }}
        interfaceSettings={mockInterfaceSettings}
        onUpdateInterfaceSettings={mockUpdateInterfaceSettings}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Ollama Local')).toBeInTheDocument();
    });

    // Click Add Provider
    await user.click(screen.getByText('+ Add Provider'));

    // Check for parallel requests checkbox
    const parallelCheckbox = screen.getByLabelText(/Enable Parallel Requests/i);
    expect(parallelCheckbox).toBeInTheDocument();
    expect(parallelCheckbox).not.toBeChecked();

    // Max parallel requests input should not be visible yet
    expect(screen.queryByText(/Max Parallel Requests/i)).not.toBeInTheDocument();

    // Enable parallel requests
    await user.click(parallelCheckbox);
    expect(parallelCheckbox).toBeChecked();

    // Max parallel requests input should now be visible
    const maxRequestsInput = screen.getByLabelText(/Max Parallel Requests/i);
    expect(maxRequestsInput).toBeInTheDocument();
    expect(maxRequestsInput).toHaveValue(2); // Default value

    // Change max requests
    // Note: The input enforces min=1, so clearing it resets to 1.
    // We append 4 (making it 24) then delete the 2 to get 4.
    await user.type(maxRequestsInput, '4{arrowleft}{backspace}');

    // Fill out other required fields
    await user.type(screen.getByLabelText(/^Name \*/i), 'Parallel Provider');
    await user.type(screen.getByLabelText(/^Base URL \*/i), 'http://localhost:11434');
    await user.type(screen.getByLabelText(/^Model Name \*/i), 'llama3');

    // Submit form
    await user.click(screen.getByText('Add Provider'));

    // Verify API call
    await waitFor(() => {
      expect(apiClient.createProvider).toHaveBeenCalledWith(expect.objectContaining({
        name: 'Parallel Provider',
        parallel_requests_enabled: true,
        max_parallel_requests: 4,
      }));
    });
  });
});
