import React, { useState } from 'react';
import type { Clue } from '../types';

interface ClueReviewQueueProps {
  clues: Clue[];
  apiKey: string;
  onReviewSubmit: () => void;
}

export const ClueReviewQueue: React.FC<ClueReviewQueueProps> = ({ clues, apiKey, onReviewSubmit }) => {
  const [selectedClue, setSelectedClue] = useState<Clue | null>(clues[0] || null);
  const [reviewer, setReviewer] = useState('Analyst_Tharun');
  const [notes, setNotes] = useState('');
  const [statusAction, setStatusAction] = useState<'supported' | 'rejected' | 'under_review'>('supported');
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const handleReview = async () => {
    if (!selectedClue) return;
    if (!apiKey) {
      setMessage('Error: Enter an API key in the top bar to submit reviews.');
      return;
    }

    setSubmitting(true);
    setMessage(null);
    try {
      const res = await fetch(`/api/v1/clues/${encodeURIComponent(selectedClue.clue_id)}/review`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey,
        },
        body: JSON.stringify({
          status: statusAction,
          reviewer,
          notes,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Review failed' }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      setMessage(`Clue status updated to ${statusAction.toUpperCase()}.`);
      onReviewSubmit();
    } catch (err: any) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '20px', height: '100%' }}>
      {/* Left List */}
      <div style={{ background: '#0d1524', border: '1px solid #1c2d4a', borderRadius: '8px', padding: '16px', overflowY: 'auto' }}>
        <h3 style={{ fontSize: '14px', color: '#94a3b8', marginBottom: '12px', textTransform: 'uppercase' }}>
          Candidate Relationships ({clues.length})
        </h3>
        {clues.length === 0 && <div style={{ color: '#64748b', fontSize: '13px' }}>No candidate clues awaiting review.</div>}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {clues.map(c => {
            const isSel = selectedClue?.clue_id === c.clue_id;
            return (
              <div
                key={c.clue_id}
                onClick={() => setSelectedClue(c)}
                style={{
                  padding: '12px',
                  borderRadius: '6px',
                  background: isSel ? '#152238' : '#0a0f1a',
                  border: `1px solid ${isSel ? '#00e5ff' : '#1c2d4a'}`,
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ fontWeight: 600, fontSize: '13px', color: '#f0f6fc' }}>
                    {c.handle_a} ↔ {c.handle_b}
                  </span>
                  <span
                    style={{
                      fontSize: '11px',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      background: c.score >= 0.7 ? '#1e3a5f' : '#1c2d4a',
                      color: c.score >= 0.7 ? '#00e5ff' : '#94a3b8',
                      fontWeight: 600,
                    }}
                  >
                    {(c.score * 100).toFixed(0)}%
                  </span>
                </div>
                <div style={{ fontSize: '11px', color: '#64748b' }}>
                  Status: <span style={{ color: c.status === 'candidate' ? '#f59e0b' : '#10b981' }}>{c.status}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right Details & Decision Form */}
      {selectedClue ? (
        <div style={{ background: '#0d1524', border: '1px solid #1c2d4a', borderRadius: '8px', padding: '20px', overflowY: 'auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #1c2d4a', paddingBottom: '16px', marginBottom: '16px' }}>
            <div>
              <h2 style={{ fontSize: '18px', color: '#f0f6fc', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>{selectedClue.handle_a}</span>
                <span style={{ color: '#00e5ff', fontSize: '14px' }}>SAME_AS</span>
                <span>{selectedClue.handle_b}</span>
              </h2>
              <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                Clue ID: <code style={{ color: '#94a3b8' }}>{selectedClue.clue_id}</code> | Method: {selectedClue.scoring_method_version}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '24px', fontWeight: 700, color: '#00e5ff' }}>
                {(selectedClue.score * 100).toFixed(1)}%
              </div>
              <div style={{ fontSize: '11px', color: '#64748b' }}>Heuristic Similarity</div>
            </div>
          </div>

          {/* Signal Breakdown */}
          <h4 style={{ fontSize: '13px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '10px' }}>Evidence Signals</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px', marginBottom: '20px' }}>
            {Object.entries(selectedClue.signals || {}).map(([key, sig]) => (
              <div key={key} style={{ background: '#0a0f1a', padding: '12px', borderRadius: '6px', border: '1px solid #1c2d4a' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: '#f0f6fc', marginBottom: '4px' }}>{sig.name}</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#64748b', marginBottom: '6px' }}>
                  <span>Weight: {sig.weight}</span>
                  <span style={{ color: sig.status === 'available' ? '#00e5ff' : '#64748b' }}>
                    {sig.status === 'available' ? `Score: ${sig.value}` : 'MISSING'}
                  </span>
                </div>
                <div style={{ fontSize: '11px', color: '#94a3b8' }}>{sig.details}</div>
              </div>
            ))}
          </div>

          {/* Contradictions & Explanations */}
          {selectedClue.contradictions && selectedClue.contradictions.length > 0 && (
            <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', borderRadius: '6px', padding: '12px', marginBottom: '16px' }}>
              <div style={{ fontWeight: 600, fontSize: '12px', color: '#f87171', marginBottom: '4px' }}>Contradictory / Cautionary Signals:</div>
              <ul style={{ fontSize: '12px', color: '#fca5a5', paddingLeft: '16px' }}>
                {selectedClue.contradictions.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </div>
          )}

          {/* Explanation Breakdown */}
          {selectedClue.explanation && selectedClue.explanation.length > 0 && (
            <div style={{ background: '#0a0f1a', border: '1px solid #1c2d4a', borderRadius: '6px', padding: '12px', marginBottom: '16px' }}>
              <div style={{ fontWeight: 600, fontSize: '12px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '6px' }}>
                Scoring Explanation & Evidence Grounding
              </div>
              <ul style={{ fontSize: '12px', color: '#cbd5e1', paddingLeft: '16px', lineHeight: '1.6' }}>
                {selectedClue.explanation.map((exp, i) => (
                  <li key={i}>{exp}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Evidence IDs */}
          {selectedClue.evidence_ids && selectedClue.evidence_ids.length > 0 && (
            <div style={{ background: '#0a0f1a', border: '1px solid #1c2d4a', borderRadius: '6px', padding: '12px', marginBottom: '16px' }}>
              <div style={{ fontWeight: 600, fontSize: '12px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '6px' }}>
                Supporting Evidence IDs ({selectedClue.evidence_ids.length})
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {selectedClue.evidence_ids.map((id, i) => (
                  <span
                    key={i}
                    style={{
                      fontSize: '11px',
                      fontFamily: 'monospace',
                      background: '#152238',
                      color: '#00e5ff',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      border: '1px solid #1c2d4a',
                    }}
                  >
                    {id}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Review Decision Form */}
          <div style={{ background: '#0a0f1a', border: '1px solid #1c2d4a', borderRadius: '6px', padding: '16px', marginTop: '20px' }}>
            <h4 style={{ fontSize: '13px', color: '#f0f6fc', marginBottom: '12px' }}>Analyst Attribution Review</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>Decision</label>
                <select
                  value={statusAction}
                  onChange={e => setStatusAction(e.target.value as any)}
                  style={{ width: '100%', background: '#0d1524', border: '1px solid #1c2d4a', padding: '8px', borderRadius: '4px', color: '#f0f6fc' }}
                >
                  <option value="supported">Supported (Strong Corroborating Clue)</option>
                  <option value="under_review">Under Review (Further Telemetry Needed)</option>
                  <option value="rejected">Rejected (False Positive / Artifact Leaked)</option>
                </select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>Reviewer Name</label>
                <input
                  type="text"
                  value={reviewer}
                  onChange={e => setReviewer(e.target.value)}
                  style={{ width: '100%', background: '#0d1524', border: '1px solid #1c2d4a', padding: '8px', borderRadius: '4px', color: '#f0f6fc' }}
                />
              </div>
            </div>
            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>Investigation & Justification Notes</label>
              <textarea
                rows={3}
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="Detail rationale, e.g. shared Tox ID matches loader source code release."
                style={{ width: '100%', background: '#0d1524', border: '1px solid #1c2d4a', padding: '8px', borderRadius: '4px', color: '#f0f6fc' }}
              />
            </div>
            <button
              onClick={handleReview}
              disabled={submitting}
              style={{
                background: '#00e5ff',
                color: '#080c14',
                padding: '8px 18px',
                borderRadius: '4px',
                fontWeight: 600,
                fontSize: '13px',
              }}
            >
              {submitting ? 'Persisting to Graph...' : 'Submit Decision'}
            </button>
            {message && (
              <span style={{ marginLeft: '12px', fontSize: '12px', color: message.startsWith('Error') ? '#ef4444' : '#10b981' }}>
                {message}
              </span>
            )}
          </div>
        </div>
      ) : (
        <div style={{ background: '#0d1524', border: '1px solid #1c2d4a', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>
          Select a candidate relationship to inspect evidence and review.
        </div>
      )}
    </div>
  );
};
