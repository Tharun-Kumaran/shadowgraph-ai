import type { Clue, DashboardMetrics, GraphElements, GraphRAGResponse } from '../types';

const API_BASE = '/api/v1';

export const apiService = {
  async getMetrics(): Promise<DashboardMetrics> {
    const res = await fetch(`${API_BASE}/dashboard/metrics`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return res.json();
  },

  async getGraphElements(types?: string[], status?: string, search?: string): Promise<GraphElements> {
    const params = new URLSearchParams();
    if (types && types.length > 0) {
      types.forEach(t => params.append('types', t));
    }
    if (status) params.append('status', status);
    if (search) params.append('search', search);

    const res = await fetch(`${API_BASE}/graph/elements?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return res.json();
  },

  async getEntityDetails(uid: string): Promise<any> {
    const res = await fetch(`${API_BASE}/entities/${encodeURIComponent(uid)}`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return res.json();
  },

  async getClues(status?: string): Promise<Clue[]> {
    const url = status ? `${API_BASE}/clues?status=${encodeURIComponent(status)}` : `${API_BASE}/clues`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return res.json();
  },

  async reviewClue(clueId: string, status: string, reviewer: string, notes: string, apiKey: string): Promise<any> {
    const res = await fetch(`${API_BASE}/clues/${encodeURIComponent(clueId)}/review`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
      },
      body: JSON.stringify({ status, reviewer, notes }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Review failed' }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  async uploadFile(file: File, apiKey: string): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/ingest/upload`, {
      method: 'POST',
      headers: {
        'X-API-Key': apiKey,
      },
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  async askGraphRAG(question: string, focusUid?: string): Promise<GraphRAGResponse> {
    const res = await fetch(`${API_BASE}/graphrag/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, focus_entity_uid: focusUid }),
    });
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return res.json();
  },

  async draftCertInReport(data: any): Promise<any> {
    const res = await fetch(`${API_BASE}/incidents/draft-certin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return res.json();
  },

  async getTorStatus(): Promise<{ configured: boolean; enabled: boolean; proxy: string; reachable: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/ingest/tor-status`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    return res.json();
  },

  async collectSource(url: string, sourceId?: string, sourceName?: string, apiKey?: string): Promise<any> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (apiKey) {
      headers['X-API-Key'] = apiKey;
    }
    const res = await fetch(`${API_BASE}/ingest/collect`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        url,
        source_id: sourceId || undefined,
        source_name: sourceName || undefined,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Collection failed' }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },
};

