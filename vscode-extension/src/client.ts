/**
 * HTTP client for the Shared Synapse REST API.
 * Handles JWT bearer auth and transparent token refresh via VS Code SecretStorage.
 */
import * as https from 'https';
import * as http from 'http';
import { URL } from 'url';
import type { SecretStorage } from 'vscode';

export class SynapseClient {
  private baseUrl: string;
  private accessToken: string;
  private refreshToken: string;
  private apiToken: string;
  private secrets: SecretStorage;

  constructor(
    baseUrl: string,
    accessToken: string,
    refreshToken: string,
    secrets: SecretStorage,
    apiToken = '',
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    this.apiToken = apiToken;
    this.secrets = secrets;
  }

  // ---------------------------------------------------------------------------
  // HTTP helpers
  // ---------------------------------------------------------------------------

  private request<T>(method: string, path: string, body?: unknown): Promise<T> {
    return new Promise((resolve, reject) => {
      const url = new URL(`${this.baseUrl}${path}`);
      const isHttps = url.protocol === 'https:';
      const lib = isHttps ? https : http;
      const bodyStr = body ? JSON.stringify(body) : undefined;
      const options: http.RequestOptions = {
        hostname: url.hostname,
        port: url.port || (isHttps ? 443 : 80),
        path: url.pathname + url.search,
        method,
        headers: {
          'Content-Type': 'application/json',
          ...((this.apiToken || this.accessToken)
            ? { Authorization: `Bearer ${this.apiToken || this.accessToken}` }
            : {}),
          ...(bodyStr ? { 'Content-Length': Buffer.byteLength(bodyStr) } : {}),
        },
      };

      const req = lib.request(options, (res) => {
        let data = '';
        res.on('data', (chunk) => (data += chunk));
        res.on('end', () => {
          try {
            const parsed = JSON.parse(data);
            if ((res.statusCode ?? 0) >= 400) {
              reject(new Error(`HTTP ${res.statusCode}: ${data}`));
            } else {
              resolve(parsed as T);
            }
          } catch {
            reject(new Error(`Invalid JSON response: ${data}`));
          }
        });
      });

      req.on('error', reject);
      if (bodyStr) req.write(bodyStr);
      req.end();
    });
  }

  private async requestWithRefresh<T>(method: string, path: string, body?: unknown): Promise<T> {
    try {
      return await this.request<T>(method, path, body);
    } catch (err: unknown) {
      if (this.apiToken) {
        throw err;
      }

      if (err instanceof Error && err.message.startsWith('HTTP 401') && this.refreshToken) {
        const refreshed = await this.doRefresh();
        if (refreshed) {
          return this.request<T>(method, path, body);
        }
      }
      throw err;
    }
  }

  private async doRefresh(): Promise<boolean> {
    try {
      const data = await this.request<{ access_token: string }>('POST', '/auth/refresh', {
        refresh_token: this.refreshToken,
      });
      this.accessToken = data.access_token;
      await this.secrets.store('sharedSynapse.accessToken', this.accessToken);
      return true;
    } catch {
      return false;
    }
  }

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  get<T>(path: string): Promise<T> {
    return this.requestWithRefresh<T>('GET', path);
  }

  post<T>(path: string, body?: unknown): Promise<T> {
    return this.requestWithRefresh<T>('POST', path, body);
  }

  async healthCheck(): Promise<void> {
    await this.request('GET', '/health');
  }

  async listSynapses(): Promise<{ name: string; active: boolean }[]> {
    const data = await this.get<{ synapses: { name: string; active: boolean }[] }>('/api/synapses');
    return data.synapses;
  }

  async getSynapseResources(name: string): Promise<{
    skills: { id: string; name: string; description: string; type: string }[];
    rules: { id: string; name: string; description: string; type: string }[];
    tools: { id: string; name: string; description: string; type: string }[];
  }> {
    return this.get(`/api/synapses/${encodeURIComponent(name)}/resources`);
  }

  async getResourceDetail(resourceType: 'skill' | 'rule' | 'tool', resourceId: string): Promise<{
    id: string;
    name: string;
    description: string;
    type: string;
    content: string;
  }> {
    return this.get(`/api/resources/${resourceType}/${encodeURIComponent(resourceId)}`);
  }

  async activateSynapse(name: string): Promise<void> {
    await this.post(`/api/synapses/${encodeURIComponent(name)}/activate`);
  }

  async deactivateSynapse(name: string): Promise<void> {
    await this.post(`/api/synapses/${encodeURIComponent(name)}/deactivate`);
  }

  async searchKnowledge(query: string): Promise<{ results: { document_id: string; chunk_content: string; score: number }[] }> {
    return this.get(`/api/search?query=${encodeURIComponent(query)}`);
  }

  async addKnowledge(
    id: string,
    type: string,
    content: string,
    metadata?: Record<string, unknown>,
  ): Promise<void> {
    await this.post('/api/knowledge', { id, type, content, metadata });
  }

  async login(username: string, password: string): Promise<{ access_token: string; refresh_token: string; role: string }> {
    const data = await this.request<{ access_token: string; refresh_token: string; role: string }>(
      'POST', '/auth/login', { username, password }
    );
    this.apiToken = '';
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    await this.secrets.delete('sharedSynapse.apiToken');
    await this.secrets.store('sharedSynapse.accessToken', data.access_token);
    await this.secrets.store('sharedSynapse.refreshToken', data.refresh_token);
    return data;
  }

  async useApiToken(apiToken: string): Promise<void> {
    this.apiToken = apiToken.trim();
    this.accessToken = '';
    this.refreshToken = '';
    await this.secrets.delete('sharedSynapse.accessToken');
    await this.secrets.delete('sharedSynapse.refreshToken');
    await this.secrets.store('sharedSynapse.apiToken', this.apiToken);
  }
}
