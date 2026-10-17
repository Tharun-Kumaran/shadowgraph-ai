import React, { useState } from 'react';
import { apiService } from '../services/api';
import type { GraphRAGResponse } from '../types';

export const AIAssistant: React.FC = () => {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<GraphRAGResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const res = await apiService.askGraphRAG(question);
      setResponse(res);
    } catch (err: any) {
      setError(err.message || 'Failed to query GraphRAG service');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: '#0d1524', border: '1px solid #1c2d4a', borderRadius: '8px', padding: '20px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: '16px' }}>
        <h2 style={{ fontSize: '16px', color: '#f0f6fc', marginBottom: '4px' }}>Local AI Grounded Assistant (GraphRAG)</h2>
        <p style={{ fontSize: '12px', color: '#94a3b8' }}>
          Ask natural-language CTI questions. Answers are synthesized directly from retrieved Neo4j evidence without hallucinating unobserved facts.
        </p>
      </div>

      {/* Answer View */}
      <div style={{ flex: 1, overflowY: 'auto', background: '#090e17', border: '1px solid #1c2d4a', borderRadius: '6px', padding: '16px', marginBottom: '16px' }}>
        {response ? (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <span
                style={{
                  fontSize: '11px',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  background: response.llm_available ? '#064e3b' : '#3b1812',
                  color: response.llm_available ? '#34d399' : '#f87171',
                  fontWeight: 600,
                }}
              >
                {response.llm_available ? `Model: ${response.model}` : 'Deterministic Fallback'}
              </span>
            </div>
            <div style={{ fontSize: '13px', lineHeight: '1.6', color: '#f0f6fc', whiteSpace: 'pre-wrap', marginBottom: '16px' }}>
              {response.answer}
            </div>

            {/* Evidence References */}
            {response.evidence_references && response.evidence_references.length > 0 && (
              <div style={{ borderTop: '1px solid #1c2d4a', paddingTop: '12px', marginTop: '12px' }}>
                <h4 style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '6px' }}>Citing Graph Evidence:</h4>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {response.evidence_references.map((ev, i) => (
                    <span
                      key={i}
                      style={{
                        fontSize: '10px',
                        background: '#152238',
                        color: '#00e5ff',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        border: '1px solid #1c2d4a',
                        fontFamily: 'monospace',
                      }}
                    >
                      {ev.other_uid || ev.root_uid || ev.data?.clue_id || 'evidence-item'}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ color: '#64748b', fontSize: '13px', textAlign: 'center', marginTop: '40px' }}>
            Enter an investigation inquiry below. Example: <em>"What candidate relationships exist between pepela and Spirigatito?"</em>
          </div>
        )}
      </div>

      {error && <div style={{ color: '#ef4444', fontSize: '12px', marginBottom: '10px' }}>{error}</div>}

      {/* Input */}
      <form onSubmit={handleAsk} style={{ display: 'flex', gap: '10px' }}>
        <input
          type="text"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          placeholder="Ask about handles, shared technical artifacts, CVEs..."
          style={{
            flex: 1,
            background: '#090e17',
            border: '1px solid #1c2d4a',
            padding: '10px 14px',
            borderRadius: '6px',
            color: '#f0f6fc',
            fontSize: '13px',
          }}
        />
        <button
          type="submit"
          disabled={loading}
          style={{
            background: '#00e5ff',
            color: '#080c14',
            padding: '0 20px',
            borderRadius: '6px',
            fontWeight: 600,
            fontSize: '13px',
          }}
        >
          {loading ? 'Synthesizing...' : 'Query'}
        </button>
      </form>
    </div>
  );
};
