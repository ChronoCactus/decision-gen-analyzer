import {
  ADR, ADRListResponse, AnalyzeADRRequest, GenerateADRRequest, RefinePersonasRequest, RefineOriginalPromptRequest,
  TaskResponse, TaskStatus, Persona, DefaultModelConfig,
  ProvidersListResponse, LLMProvider, CreateProviderRequest, UpdateProviderRequest,
  PersonaConfig, PersonaCreateRequest, PersonaUpdateRequest, PersonaGenerateRequest, PersonaRefineRequest,
  ExportRequest, ImportResponse, ExportFormat,
  MCPServersListResponse, MCPServerConfig, CreateMCPServerRequest, UpdateMCPServerRequest,
  MCPToolsListResponse, UpdateMCPToolRequest, DiscoverToolsResponse,
  MCPStoredResult, MCPResultsListResponse
} from '@/types/api';

const DEFAULT_API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private apiBaseUrl: string = DEFAULT_API_BASE_URL;
  private configFetchPromise: Promise<void> | null = null;

  /**
   * Fetch the API configuration from the backend to support LAN discovery.
   * This allows the frontend to dynamically discover the backend URL when
   * running on different machines in the same network.
   * 
   * Strategy:
   * 1. If NEXT_PUBLIC_API_URL is explicitly set to a network IP, use it
   * 2. Otherwise, infer the backend URL from the current window location
   *    (same host as frontend, but port 8000)
   * 3. Fetch config from that URL to get the actual backend URL
   * 4. Fall back to localhost if all else fails
   */
  /**
   * Reset config state for testing purposes
   * @internal For testing only
   */
  _resetConfigForTesting(): void {
    this.configFetchPromise = null;
    this.apiBaseUrl = DEFAULT_API_BASE_URL;
  }

  /**
   * Set test mode to bypass config fetching
   * @internal For testing only
   */
  _setTestMode(testApiUrl: string): void {
    this.configFetchPromise = Promise.resolve(); // Skip config fetch
    this.apiBaseUrl = testApiUrl;
  }

  private async fetchConfig(): Promise<void> {
    // If already fetching or fetched, reuse the same promise
    if (this.configFetchPromise) {
      return this.configFetchPromise;
    }

    // Create the fetch promise and store it to prevent concurrent fetches
    this.configFetchPromise = this._doFetchConfig();
    return this.configFetchPromise;
  }

  private async _doFetchConfig(): Promise<void> {

    // If NEXT_PUBLIC_API_URL is already set to a non-localhost value, use it directly
    if (DEFAULT_API_BASE_URL !== 'http://localhost:8000') {
      console.log('Using configured API base URL:', DEFAULT_API_BASE_URL);
      this.apiBaseUrl = DEFAULT_API_BASE_URL;
      return;
    }

    // Infer the backend URL from the current window location
    // For LAN access: If user accessed frontend via http://192.168.0.58:3003, backend is likely at http://192.168.0.58:8000
    // For production with LB: If accessed via https://mywebsite.mydomain.com, backend is at same host (no port needed)
    let inferredBackendUrl = DEFAULT_API_BASE_URL;

    if (typeof window !== 'undefined') {
      const protocol = window.location.protocol;
      const hostname = window.location.hostname;
      const port = window.location.port;

      // Only infer if not running on localhost (which would be development mode)
      if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
        // If accessed with a port (e.g., :3000, :3003), assume backend is on port 8000 (LAN mode)
        // If accessed without a port (e.g., production with LB), assume backend is on same host
        if (port && port !== '80' && port !== '443') {
          // LAN mode: frontend on custom port, backend on 8000
          inferredBackendUrl = `${protocol}//${hostname}:8000`;
          console.log('Inferred backend URL (LAN mode):', inferredBackendUrl);
        } else {
          // Production mode: accessed via standard port (80/443) or no port
          // Backend is on same host (load balancer handles routing)
          inferredBackendUrl = `${protocol}//${hostname}`;
          console.log('Inferred backend URL (production mode):', inferredBackendUrl);
        }
      }
    }

    // Try to discover the backend URL
    try {
      console.log('Attempting to fetch config from:', `${inferredBackendUrl}/api/v1/config`);
      const response = await fetch(`${inferredBackendUrl}/api/v1/config`, {
        // Add timeout to fail fast if backend is not responding
        signal: AbortSignal.timeout(5000)
      });

      if (response.ok) {
        const config = await response.json();
        if (config.api_base_url) {
          this.apiBaseUrl = config.api_base_url;
          console.log('✅ API base URL configured:', this.apiBaseUrl);
          if (config.lan_discovery_enabled) {
            console.log('🌐 LAN discovery is enabled on backend');
          }
        } else {
          // Config endpoint exists but no URL provided, use inferred URL
          this.apiBaseUrl = inferredBackendUrl;
          console.log('ℹ️ Using inferred backend URL:', this.apiBaseUrl);
        }
      } else {
        console.warn('⚠️ Failed to fetch API config (HTTP %d), using inferred URL:', response.status, inferredBackendUrl);
        this.apiBaseUrl = inferredBackendUrl;
      }
    } catch (error) { 
      // If config fetch fails, use inferred URL as fallback
      console.warn('⚠️ Failed to fetch API config, using inferred URL:', inferredBackendUrl, error);
      this.apiBaseUrl = inferredBackendUrl;
    }
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    // Ensure config is fetched before making requests
    await this.fetchConfig();

    const url = `${this.apiBaseUrl}${endpoint}`;
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const errorText = await response.text();
      let errorMessage = `API request failed: ${response.status} ${response.statusText}`;

      try {
        const errorJson = JSON.parse(errorText);
        if (errorJson.detail) {
          errorMessage = errorJson.detail;
        }
      } catch {
        // If not JSON, use the text as-is
        if (errorText) {
          errorMessage = errorText;
        }
      }

      const error = new Error(errorMessage);
      // Add status code to error for better handling
      (error as any).status = response.status;
      throw error;
    }

    return response.json();
  }

  // ADR operations
  async getADRs(limit = 50, offset = 0): Promise<ADRListResponse> {
    return this.request<ADRListResponse>(`/api/v1/adrs/?limit=${limit}&offset=${offset}`);
  }

  async getADR(adrId: string): Promise<ADR> {
    return this.request<ADR>(`/api/v1/adrs/${adrId}`);
  }

  async deleteADR(adrId: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/api/v1/adrs/${adrId}`, {
      method: 'DELETE',
    });
  }

  async refinePersonas(adrId: string, request: RefinePersonasRequest): Promise<TaskResponse> {
    return this.request<TaskResponse>(`/api/v1/adrs/${adrId}/refine-personas`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async refineOriginalPrompt(adrId: string, request: RefineOriginalPromptRequest): Promise<TaskResponse> {
    return this.request<TaskResponse>(`/api/v1/adrs/${adrId}/refine-original-prompt`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async updateADRStatus(adrId: string, status: string): Promise<{ message: string; adr: ADR }> {
    return this.request<{ message: string; adr: ADR }>(`/api/v1/adrs/${adrId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  }

  async pushADRToRAG(adrId: string): Promise<{ message: string; adr_id: string; title: string }> {
    return this.request<{ message: string; adr_id: string; title: string }>(`/api/v1/adrs/${adrId}/push-to-rag`, {
      method: 'POST',
    });
  }

  async getADRRAGStatus(adrId: string): Promise<{ adr_id: string; exists_in_rag: boolean; lightrag_doc_id?: string; error?: string }> {
    return this.request<{ adr_id: string; exists_in_rag: boolean; lightrag_doc_id?: string; error?: string }>(`/api/v1/adrs/${adrId}/rag-status`);
  }

  async getCacheStatus(): Promise<{ is_rebuilding: boolean; last_sync_time?: number; error?: string }> {
    return this.request<{ is_rebuilding: boolean; last_sync_time?: number; error?: string }>('/api/v1/adrs/cache/status');
  }

  async getCacheRebuildStatus(): Promise<{ is_rebuilding: boolean; error?: string }> {
    return this.request<{ is_rebuilding: boolean; error?: string }>('/api/v1/adrs/cache/rebuild-status');
  }

  async getPersonas(): Promise<{ personas: Persona[] }> {
    return this.request<{ personas: Persona[] }>('/api/v1/adrs/personas');
  }

  async getDefaultModelConfig(): Promise<DefaultModelConfig> {
    return this.request<DefaultModelConfig>('/api/v1/adrs/config/model');
  }

  // Analysis operations
  async analyzeADR(request: AnalyzeADRRequest): Promise<TaskResponse> {
    return this.request<TaskResponse>('/api/v1/analysis/analyze', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getAnalysisTaskStatus(taskId: string): Promise<TaskStatus> {
    return this.request<TaskStatus>(`/api/v1/analysis/task/${taskId}`);
  }

  // Generation operations
  async generateADR(request: GenerateADRRequest): Promise<TaskResponse> {
    return this.request<TaskResponse>('/api/v1/generation/generate', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getGenerationTaskStatus(taskId: string): Promise<TaskStatus> {
    return this.request<TaskStatus>(`/api/v1/generation/task/${taskId}`);
  }

  // Export/Import operations
  async exportSingleADR(adrId: string, format: ExportFormat | string = ExportFormat.VERSIONED_JSON): Promise<Blob> {
    await this.fetchConfig();
    const url = `${this.apiBaseUrl}/api/v1/adrs/${adrId}/export?format=${format}`;
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`Export failed: ${response.status} ${response.statusText}`);
    }

    return response.blob();
  }

  async exportAllADRs(format: ExportFormat | string = ExportFormat.VERSIONED_JSON, adrIds?: string[]): Promise<Blob> {
    await this.fetchConfig();
    const url = `${this.apiBaseUrl}/api/v1/adrs/export`;

    const requestBody: ExportRequest = {
      format,
      adr_ids: adrIds,
    };

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      throw new Error(`Export failed: ${response.status} ${response.statusText}`);
    }

    return response.blob();
  }

  async importADRsFromFiles(files: File[], overwriteExisting: boolean = false): Promise<ImportResponse> {
    const results: ImportResponse = {
      message: '',
      imported_count: 0,
      skipped_count: 0,
      errors: [],
      imported_ids: [],
    };

    for (const file of files) {
      try {
        const formData = new FormData();
        formData.append('file', file);

        await this.fetchConfig();
        const url = `${this.apiBaseUrl}/api/v1/adrs/import/file?overwrite_existing=${overwriteExisting}`;
        const response = await fetch(url, {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          throw new Error(`Import failed for ${file.name}: ${response.status} ${response.statusText}`);
        }

        const result: ImportResponse = await response.json();
        results.imported_count += result.imported_count;
        results.skipped_count = (results.skipped_count || 0) + (result.skipped_count || 0);
        if (result.errors) {
          results.errors = [...(results.errors || []), ...result.errors.map((e: string) => `${file.name}: ${e}`)];
        }
        if (result.imported_ids) {
          results.imported_ids = [...(results.imported_ids || []), ...result.imported_ids];
        }
      } catch (error) {
        results.errors = [...(results.errors || []), `${file.name}: ${error instanceof Error ? error.message : 'Unknown error'}`];
      }
    }

    results.message = `Import completed: ${results.imported_count} imported, ${results.skipped_count} skipped`;
    return results;
  }

  // Queue operations
  async getQueueStatus(): Promise<{
    total_tasks: number;
    active_tasks: number;
    pending_tasks: number;
    reserved_tasks: number;
    workers_online: number;
  }> {
    return this.request('/api/v1/queue/status');
  }

  async getQueueTasks(): Promise<{
    tasks: Array<{
      task_id: string;
      task_name: string;
      status: string;
      position: number | null;
      args: unknown[];
      kwargs: Record<string, unknown>;
      worker: string | null;
      started_at: number | null;
      eta: string | null;
    }>;
  }> {
    return this.request('/api/v1/queue/tasks');
  }

  async getTaskInfo(taskId: string): Promise<{
    task_id: string;
    task_name: string;
    status: string;
    position: number | null;
    args: unknown[];
    kwargs: Record<string, unknown>;
    worker: string | null;
    started_at: number | null;
  }> {
    return this.request(`/api/v1/queue/task/${taskId}`);
  }

  async cancelTask(taskId: string, terminate: boolean = false): Promise<{
    message: string;
    task_id: string;
    cancelled: boolean;
  }> {
    return this.request(`/api/v1/queue/task/${taskId}/cancel?terminate=${terminate}`, {
      method: 'POST',
    });
  }

  async cleanupOrphanedTasks(): Promise<{
    message: string;
    cleaned_count: number;
    error_count: number;
    cleaned_tasks: Array<{
      task_id: string;
      task_name: string;
      state: string;
    }>;
    errors: string[];
  }> {
    return this.request('/api/v1/queue/cleanup-orphaned', {
      method: 'POST',
    });
  }

  async clearQueue(force: boolean = false): Promise<{
    message: string;
    revoked_active: number;
    purged_pending: number;
    cleared_redis_records: number;
    error_count: number;
    revoked_tasks: Array<{
      task_id: string;
      task_name: string;
    }>;
    errors: string[];
  }> {
    return this.request(`/api/v1/queue/clear?force=${force}`, {
      method: 'POST',
    });
  }

  // ==================== LLM Provider Management ====================

  async listProviders(): Promise<ProvidersListResponse> {
    return this.request('/api/v1/llm-providers');
  }

  async getProvider(providerId: string): Promise<LLMProvider> {
    return this.request(`/api/v1/llm-providers/${providerId}`);
  }

  async getDefaultProvider(): Promise<LLMProvider | null> {
    return this.request('/api/v1/llm-providers/default');
  }

  async createProvider(request: CreateProviderRequest): Promise<LLMProvider> {
    return this.request('/api/v1/llm-providers', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
  }

  async updateProvider(
    providerId: string,
    request: UpdateProviderRequest
  ): Promise<LLMProvider> {
    return this.request(`/api/v1/llm-providers/${providerId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
  }

  async deleteProvider(providerId: string): Promise<{
    message: string;
    deleted: boolean;
  }> {
    return this.request(`/api/v1/llm-providers/${providerId}`, {
      method: 'DELETE',
    });
  }

  // ==================== Persona Management ====================

  async getPersona(name: string): Promise<PersonaConfig> {
    return this.request(`/api/v1/adrs/personas/${name}`);
  }

  async createPersona(request: PersonaCreateRequest): Promise<{ message: string; persona: PersonaConfig }> {
    return this.request('/api/v1/adrs/personas', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
  }

  async updatePersona(name: string, request: PersonaUpdateRequest): Promise<{ message: string; persona: PersonaConfig }> {
    return this.request(`/api/v1/adrs/personas/${name}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
  }

  async deletePersona(name: string): Promise<{ message: string }> {
    return this.request(`/api/v1/adrs/personas/${name}`, {
      method: 'DELETE',
    });
  }

  async generatePersona(request: PersonaGenerateRequest): Promise<PersonaConfig> {
    return this.request('/api/v1/adrs/personas/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
  }

  async refinePersona(request: PersonaRefineRequest): Promise<PersonaConfig> {
    return this.request('/api/v1/adrs/personas/refine', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
  }

  // ==================== MCP Server Management ====================

  async listMcpServers(): Promise<MCPServersListResponse> {
    return this.request('/api/v1/mcp-servers');
  }

  async getMcpServer(serverId: string): Promise<MCPServerConfig> {
    return this.request(`/api/v1/mcp-servers/${serverId}`);
  }

  async createMcpServer(request: CreateMCPServerRequest): Promise<MCPServerConfig> {
    return this.request('/api/v1/mcp-servers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
  }

  async updateMcpServer(serverId: string, request: UpdateMCPServerRequest): Promise<MCPServerConfig> {
    return this.request(`/api/v1/mcp-servers/${serverId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
  }

  async deleteMcpServer(serverId: string): Promise<{ message: string; deleted: boolean }> {
    return this.request(`/api/v1/mcp-servers/${serverId}`, {
      method: 'DELETE',
    });
  }

  async discoverMcpTools(serverId: string): Promise<DiscoverToolsResponse> {
    return this.request(`/api/v1/mcp-servers/${serverId}/discover-tools`, {
      method: 'POST',
    });
  }

  async listMcpTools(): Promise<MCPToolsListResponse> {
    return this.request('/api/v1/mcp-servers/tools');
  }

  async updateMcpTool(serverId: string, toolName: string, request: UpdateMCPToolRequest): Promise<{ message: string }> {
    return this.request(`/api/v1/mcp-servers/${serverId}/tools/${toolName}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
  }

  async testMcpTool(serverId: string, toolName: string, args?: Record<string, any>): Promise<{ success: boolean; result?: any; error?: string }> {
    return this.request(`/api/v1/mcp-servers/${serverId}/tools/${toolName}/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ arguments: args || {} }),
    });
  }

  // ==================== MCP Tool Results ====================

  async getMcpResult(resultId: string): Promise<MCPStoredResult> {
    return this.request(`/api/v1/mcp-results/${resultId}`);
  }

  async listMcpResults(adrId?: string): Promise<MCPResultsListResponse> {
    const params = adrId ? `?adr_id=${encodeURIComponent(adrId)}` : '';
    return this.request(`/api/v1/mcp-results${params}`);
  }

  async deleteMcpResult(resultId: string): Promise<{ message: string }> {
    return this.request(`/api/v1/mcp-results/${resultId}`, {
      method: 'DELETE',
    });
  }
}

export const apiClient = new ApiClient();
