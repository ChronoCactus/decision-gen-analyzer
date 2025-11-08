import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { apiClient } from './api';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('ApiClient', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    vi.clearAllMocks();
    // Reset apiClient to a clean state for each test
    apiClient._resetConfigForTesting();
    // Set test mode to bypass config fetching for most tests
    apiClient._setTestMode('http://localhost:8000');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Configuration and LAN Discovery', () => {
    it('should fetch config on first request', async () => {
      // Reset to allow config fetching for this test
      apiClient._resetConfigForTesting();
      
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ api_base_url: 'http://192.168.1.100:8000', lan_discovery_enabled: true }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ adrs: [], total: 0 }),
        });

      await apiClient.getADRs();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/config'),
        expect.any(Object)
      );
    });

    it('should use configured API base URL from config', async () => {
      // Reset to allow config fetching for this test
      apiClient._resetConfigForTesting();
      
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ api_base_url: 'http://192.168.1.100:8000' }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ adrs: [], total: 0 }),
        });

      await apiClient.getADRs();

      expect(mockFetch).toHaveBeenCalledWith(
        'http://192.168.1.100:8000/api/v1/adrs/?limit=50&offset=0',
        expect.any(Object)
      );
    });

    it('should handle config fetch failure gracefully', async () => {
      // Reset to allow config fetching for this test
      apiClient._resetConfigForTesting();
      
      mockFetch
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ adrs: [], total: 0 }),
        });

      await apiClient.getADRs();

      expect(mockFetch).toHaveBeenCalledTimes(2);
    });
  });

  describe('ADR Operations', () => {
    it('should get ADRs with default parameters', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ adrs: [], total: 0 }),
      });

      const result = await apiClient.getADRs();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/adrs/?limit=50&offset=0'),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      );
      expect(result).toEqual({ adrs: [], total: 0 });
    });

    it('should get ADRs with custom parameters', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ adrs: [], total: 0 }),
      });

      await apiClient.getADRs(10, 20);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/adrs/?limit=10&offset=20'),
        expect.any(Object)
      );
    });

    it('should get single ADR by ID', async () => {
      const mockADR = {
        metadata: { id: 'adr-123', title: 'Test ADR', status: 'accepted' },
        content: { context_and_problem: 'Problem', decision_outcome: 'Decision' },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockADR,
      });

      const result = await apiClient.getADR('adr-123');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/adrs/adr-123'),
        expect.any(Object)
      );
      expect(result).toEqual(mockADR);
    });

    it('should delete ADR', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'ADR deleted successfully' }),
      });

      const result = await apiClient.deleteADR('adr-123');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/adrs/adr-123'),
        expect.objectContaining({
          method: 'DELETE',
        })
      );
      expect(result).toEqual({ message: 'ADR deleted successfully' });
    });

    it('should push ADR to RAG', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          message: 'Success',
          adr_id: 'adr-123',
          title: 'Test ADR',
        }),
      });

      const result = await apiClient.pushADRToRAG('adr-123');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/adrs/adr-123/push-to-rag'),
        expect.objectContaining({
          method: 'POST',
        })
      );
      expect(result).toEqual({
        message: 'Success',
        adr_id: 'adr-123',
        title: 'Test ADR',
      });
    });

    it('should throw error on failed request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        text: async () => '',
      });

      await expect(apiClient.getADR('nonexistent')).rejects.toThrow(
        'API request failed: 404 Not Found'
      );
    });
  });

  describe('Persona Operations', () => {
    it('should get personas', async () => {
      const mockPersonas = {
        personas: [
          { value: 'technical_lead', label: 'Technical Lead', description: 'Tech focus' },
          { value: 'business_analyst', label: 'Business Analyst', description: 'Business focus' },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPersonas,
      });

      const result = await apiClient.getPersonas();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/adrs/personas'),
        expect.any(Object)
      );
      expect(result).toEqual(mockPersonas);
    });
  });

  describe('Analysis Operations', () => {
    it('should analyze ADR', async () => {
      const mockResponse = {
        task_id: 'task-123',
        status: 'pending',
        message: 'Analysis queued',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await apiClient.analyzeADR({
        adr_id: 'adr-123',
        persona: 'technical_lead',
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/analysis/analyze'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ adr_id: 'adr-123', persona: 'technical_lead' }),
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it('should get analysis task status', async () => {
      const mockStatus = {
        task_id: 'task-123',
        status: 'completed',
        result: { score: 8.5 },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStatus,
      });

      const result = await apiClient.getAnalysisTaskStatus('task-123');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/analysis/task/task-123'),
        expect.any(Object)
      );
      expect(result).toEqual(mockStatus);
    });
  });

  describe('Generation Operations', () => {
    it('should generate ADR', async () => {
      const mockResponse = {
        task_id: 'task-456',
        status: 'pending',
        message: 'Generation queued',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await apiClient.generateADR({
        prompt: 'Generate ADR for database selection',
        context: 'We need a database solution',
        tags: ['database', 'architecture'],
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/generation/generate'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('database selection'),
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it('should get generation task status', async () => {
      const mockStatus = {
        task_id: 'task-456',
        status: 'completed',
        result: { adr_id: 'adr-new' },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStatus,
      });

      const result = await apiClient.getGenerationTaskStatus('task-456');

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/generation/task/task-456'),
        expect.any(Object)
      );
      expect(result).toEqual(mockStatus);
    });
  });
});
