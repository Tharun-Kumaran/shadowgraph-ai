import React, { useEffect, useState } from 'react';
import { apiService } from './services/api';
import type { Clue, DashboardMetrics, GraphElements } from './types';
import { GraphViewer } from './components/GraphViewer';
import { ClueReviewQueue } from './components/ClueReviewQueue';
import { AIAssistant } from './components/AIAssistant';
import { IngestionExport } from './components/IngestionExport';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'graph' | 'clues' | 'ai' | 'ingest'>('graph');
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [graphData, setGraphData] = useState<GraphElements>({ nodes: [], edges: [] });
  const [clues, setClues] = useState<Clue[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [entityDetails, setEntityDetails] = useState<any | null>(null);
  const [apiKey, setApiKey] = useState('dev-shadowgraph-key');
  const [, setLoading] = useState(true);

  const loadData = async () => {
    try {
      const [m, g, c] = await Promise.all([
        apiService.getMetrics().catch(() => null),
        apiService.getGraphElements().catch(() => ({ nodes: [], edges: [] })),
        apiService.getClues().catch(() => []),
      ]);
      if (m) setMetrics(m);
      setGraphData(g);
      setClues(c);
    } catch (err) {
      console.error('Failed to load initial graph telemetry:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSelectNode = async (nodeId: string) => {
    setSelectedNodeId(nodeId);
    try {
      const details = await apiService.getEntityDetails(nodeId);
      setEntityDetails(details);
    } catch (err) {
      console.error('Failed to fetch entity details:', err);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg-primary)' }}>
      {/* Top Header */}
      <header
        style={{
          height: '56px',
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 20px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '18px', fontWeight: 800, color: 'var(--accent-cyan)', letterSpacing: '-0.5px' }}>
              SHADOWGRAPH AI
            </span>
            <span
              style={{
                fontSize: '10px',
                background: 'rgba(0, 229, 255, 0.1)',
                color: 'var(--accent-cyan)',
                border: '1px solid rgba(0, 229, 255, 0.2)',
                padding: '1px 6px',
                borderRadius: '4px',
                fontWeight: 600,
              }}
            >
              CTI v0.1
            </span>
          </div>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Connect the clues. Map the network. Investigate with confidence.
          </span>
        </div>

        {/* Navigation Tabs & API Key */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <nav style={{ display: 'flex', gap: '4px' }}>
            {[
              { id: 'graph', label: 'Investigation Graph' },
              { id: 'clues', label: `Clue Review Queue (${clues.filter(c => c.status === 'candidate').length})` },
              { id: 'ai', label: 'AI Assistant (GraphRAG)' },
              { id: 'ingest', label: 'Ingest & Export' },
            ].map(tab => {
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '4px',
                    fontSize: '12px',
                    fontWeight: 600,
                    color: active ? '#080c14' : 'var(--text-secondary)',
                    background: active ? 'var(--accent-cyan)' : 'transparent',
                    transition: 'all 0.15s',
                  }}
                >
                  {tab.label}
                </button>
              );
            })}
          </nav>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>X-API-Key:</span>
            <input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder="API Key"
              style={{
                width: '120px',
                background: 'var(--bg-primary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '4px',
                padding: '4px 8px',
                fontSize: '11px',
                color: 'var(--text-primary)',
              }}
            />
          </div>
        </div>
      </header>

      {/* Metrics Ribbon */}
      <div
        style={{
          height: '42px',
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 20px',
          gap: '24px',
          fontSize: '12px',
        }}
      >
        <span style={{ color: 'var(--text-muted)' }}>Graph Metrics:</span>
        <span style={{ color: 'var(--text-secondary)' }}>
          Observations: <strong style={{ color: 'var(--text-primary)' }}>{metrics?.observations ?? '-'}</strong>
        </span>
        <span style={{ color: 'var(--text-secondary)' }}>
          Handles: <strong style={{ color: 'var(--text-primary)' }}>{metrics?.handles ?? '-'}</strong>
        </span>
        <span style={{ color: 'var(--text-secondary)' }}>
          Indicators: <strong style={{ color: 'var(--text-primary)' }}>{metrics?.indicators ?? '-'}</strong>
        </span>
        <span style={{ color: 'var(--text-secondary)' }}>
          Candidate Clues:{' '}
          <strong style={{ color: 'var(--status-candidate)' }}>{metrics?.candidate_clues ?? '-'}</strong>
        </span>
        <span style={{ color: 'var(--text-secondary)' }}>
          Reviewed: <strong style={{ color: 'var(--status-supported)' }}>{metrics?.reviewed_clues ?? '-'}</strong>
        </span>
      </div>

      {/* Main Body */}
      <main style={{ flex: 1, padding: '16px', overflow: 'hidden' }}>
        {activeTab === 'graph' && (
          <div style={{ display: 'grid', gridTemplateColumns: selectedNodeId ? '1fr 340px' : '1fr', gap: '16px', height: '100%' }}>
            <GraphViewer data={graphData} onSelectNode={handleSelectNode} selectedNodeId={selectedNodeId} />
            {selectedNodeId && entityDetails && (
              <div
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  padding: '16px',
                  overflowY: 'auto',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <h3 style={{ fontSize: '14px', color: 'var(--text-primary)' }}>Entity Explorer</h3>
                  <button onClick={() => setSelectedNodeId(null)} style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                    ✕
                  </button>
                </div>
                <div style={{ fontSize: '12px', marginBottom: '12px' }}>
                  <div style={{ color: 'var(--text-muted)' }}>UID:</div>
                  <code style={{ color: 'var(--accent-cyan)', fontSize: '11px' }}>{selectedNodeId}</code>
                </div>
                <div style={{ fontSize: '12px', marginBottom: '16px' }}>
                  <div style={{ color: 'var(--text-muted)' }}>Type:</div>
                  <div style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{entityDetails.entity?.type || 'Node'}</div>
                </div>

                <h4 style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', textTransform: 'uppercase' }}>
                  Connections ({entityDetails.connections?.length || 0})
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {entityDetails.connections?.map((c: any, i: number) => (
                    <div
                      key={i}
                      style={{
                        padding: '6px 8px',
                        borderRadius: '4px',
                        background: 'var(--bg-primary)',
                        border: '1px solid var(--border-subtle)',
                        fontSize: '11px',
                      }}
                    >
                      <span style={{ color: 'var(--text-muted)' }}>{c.is_outgoing ? '→' : '←'} {c.rel_type}: </span>
                      <strong style={{ color: 'var(--text-primary)' }}>{c.other_label}</strong>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'clues' && <ClueReviewQueue clues={clues} apiKey={apiKey} onReviewSubmit={loadData} />}
        {activeTab === 'ai' && <AIAssistant />}
        {activeTab === 'ingest' && <IngestionExport apiKey={apiKey} />}
      </main>
    </div>
  );
};

export default App;
