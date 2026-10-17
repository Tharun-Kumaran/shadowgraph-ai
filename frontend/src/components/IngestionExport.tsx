import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import type { TorStatus, IngestReport } from '../types';

export const IngestionExport: React.FC<{ apiKey: string }> = ({ apiKey }) => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<IngestReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Live Collection State
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceName, setSourceName] = useState('');
  const [sourceId, setSourceId] = useState('');
  const [collecting, setCollecting] = useState(false);
  const [collectionResult, setCollectionResult] = useState<IngestReport | null>(null);
  const [collectionError, setCollectionError] = useState<string | null>(null);

  // Tor Status State
  const [torStatus, setTorStatus] = useState<TorStatus | null>(null);
  const [loadingTor, setLoadingTor] = useState(false);

  // CERT-In Form State
  const [certTitle, setCertTitle] = useState('Suspected Perimeter Reconnaissance');
  const [certSeverity, setCertSeverity] = useState('HIGH');
  const [certCategory, setCertCategory] = useState('Targeted Scanning / Probing');
  const [certSummary, setCertSummary] = useState('Exploit chain targeting CVE-2024-3400 observed in underground darknet forum.');
  const [certReport, setCertReport] = useState<any>(null);

  const fetchTorStatus = async () => {
    setLoadingTor(true);
    try {
      const res = await apiService.getTorStatus();
      setTorStatus(res);
    } catch (err: any) {
      console.error('Failed to get Tor status:', err);
    } finally {
      setLoadingTor(false);
    }
  };

  useEffect(() => {
    fetchTorStatus();
  }, []);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    if (!apiKey) {
      setError('Please provide an API key in the top bar before uploading data.');
      return;
    }

    setUploading(true);
    setError(null);
    try {
      const res = await apiService.uploadFile(file, apiKey);
      setUploadResult(res);
    } catch (err: any) {
      setError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleCollect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceUrl.trim()) return;
    if (!apiKey) {
      setCollectionError('Please provide an API key in the top bar before initiating collection.');
      return;
    }

    setCollecting(true);
    setCollectionError(null);
    setCollectionResult(null);

    try {
      const res = await apiService.collectSource(sourceUrl.trim(), sourceId.trim(), sourceName.trim(), apiKey);
      setCollectionResult(res);
    } catch (err: any) {
      setCollectionError(err.message || 'Collection failed');
    } finally {
      setCollecting(false);
    }
  };

  const handleGenerateCertReport = async () => {
    try {
      const draft = await apiService.draftCertInReport({
        title: certTitle,
        category: certCategory,
        severity: certSeverity,
        summary: certSummary,
        affected_systems: ['PAN-OS GlobalProtect Edge'],
        indicators: ['CVE-2024-3400', '198.51.100.24'],
        evidence_uids: ['post:SYN-POST-001', 'post:SYN-POST-004'],
        containment_actions: ['Isolated vulnerable perimeter gateway.'],
        analyst_notes: 'Evidence grounded in ShadowGraph correlated forum observations.',
      });
      setCertReport(draft);
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: '20px', height: '100%', overflowY: 'auto' }}>
      {/* Left: Ingestion & Live Collection */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
        
        {/* Tor Status & Live Collector Card */}
        <div style={{ background: '#0d1524', border: '1px solid #1c2d4a', borderRadius: '8px', padding: '18px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '15px', color: '#f0f6fc', margin: 0 }}>Live Darknet & CTI Collector</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                style={{
                  fontSize: '11px',
                  padding: '3px 8px',
                  borderRadius: '12px',
                  fontWeight: 600,
                  background: torStatus?.reachable ? '#064e3b' : '#3b1c1c',
                  color: torStatus?.reachable ? '#34d399' : '#f87171',
                  border: `1px solid ${torStatus?.reachable ? '#059669' : '#991b1b'}`,
                }}
              >
                Tor Proxy: {torStatus?.reachable ? 'ONLINE (Port 9050)' : 'OFFLINE'}
              </span>
              <button
                type="button"
                onClick={fetchTorStatus}
                disabled={loadingTor}
                style={{
                  background: '#152238',
                  border: '1px solid #1c2d4a',
                  color: '#94a3b8',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  fontSize: '10px',
                  cursor: 'pointer',
                }}
              >
                {loadingTor ? '...' : 'Refresh'}
              </button>
            </div>
          </div>

          <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '12px', lineHeight: 1.5 }}>
            Automated fetch of live Cyber Threat Intelligence from authorized <code>.onion</code> hidden services (via safe <code>socks5h://</code>) or external public HTTPS feeds with built-in SSRF defenses.
          </p>

          {torStatus && !torStatus.reachable && (
            <div style={{ background: '#181216', border: '1px solid #582424', borderRadius: '6px', padding: '10px', marginBottom: '14px', fontSize: '11px', color: '#fca5a5' }}>
              <strong>Notice:</strong> {torStatus.message}. Real dark-web <code>.onion</code> sources require a local Tor daemon. Public <code>https://</code> CTI feeds can still be ingested directly.
            </div>
          )}

          <form onSubmit={handleCollect} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                Source Target URL (.onion or https://)
              </label>
              <input
                type="text"
                placeholder="e.g. http://expyuzz5wqqfdgah56...5fd.onion/dump.json or https://raw.githubusercontent.com/..."
                value={sourceUrl}
                onChange={e => setSourceUrl(e.target.value)}
                style={{
                  width: '100%',
                  background: '#090e17',
                  border: '1px solid #1c2d4a',
                  padding: '8px 10px',
                  borderRadius: '4px',
                  color: '#f0f6fc',
                  fontSize: '12px',
                  fontFamily: 'monospace',
                }}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                  Source ID (optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. src-darknet-leak-01"
                  value={sourceId}
                  onChange={e => setSourceId(e.target.value)}
                  style={{
                    width: '100%',
                    background: '#090e17',
                    border: '1px solid #1c2d4a',
                    padding: '6px 10px',
                    borderRadius: '4px',
                    color: '#f0f6fc',
                    fontSize: '12px',
                  }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>
                  Source Name / Forum (optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. ExploitForum Leak"
                  value={sourceName}
                  onChange={e => setSourceName(e.target.value)}
                  style={{
                    width: '100%',
                    background: '#090e17',
                    border: '1px solid #1c2d4a',
                    padding: '6px 10px',
                    borderRadius: '4px',
                    color: '#f0f6fc',
                    fontSize: '12px',
                  }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '4px' }}>
              <div style={{ fontSize: '11px', color: '#64748b' }}>
                SSRF Filter • 100KB Stream Bound • No Redirects • Strict Provenance
              </div>
              <button
                type="submit"
                disabled={collecting || !sourceUrl.trim()}
                style={{
                  background: '#00e5ff',
                  color: '#080c14',
                  padding: '8px 16px',
                  borderRadius: '4px',
                  fontWeight: 600,
                  fontSize: '12px',
                  cursor: collecting ? 'not-allowed' : 'pointer',
                }}
              >
                {collecting ? 'Fetching & Ingesting...' : 'Collect & Ingest'}
              </button>
            </div>
          </form>

          {collectionError && (
            <div style={{ color: '#ef4444', background: '#221115', border: '1px solid #6b1d28', borderRadius: '4px', padding: '10px', fontSize: '12px', marginTop: '12px' }}>
              {collectionError}
            </div>
          )}

          {collectionResult && (
            <div style={{ marginTop: '14px', background: '#090e17', padding: '14px', borderRadius: '6px', border: '1px solid #10b981', fontSize: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span style={{ color: '#10b981', fontWeight: 600 }}>Batch {collectionResult.batch_id} Ingested</span>
                <span style={{ background: '#064e3b', color: '#34d399', padding: '2px 6px', borderRadius: '4px', fontSize: '10px' }}>
                  Live Provenance (synthetic: false)
                </span>
              </div>
              <div style={{ color: '#94a3b8', marginBottom: '6px' }}>
                Total: {collectionResult.total_records} | Accepted: {collectionResult.accepted} | Rejected: {collectionResult.rejected?.length || 0}
              </div>
              {collectionResult.extractions && Object.keys(collectionResult.extractions).length > 0 && (
                <div style={{ marginTop: '6px', borderTop: '1px solid #1c2d4a', paddingTop: '6px', fontSize: '11px', color: '#38bdf8' }}>
                  Extracted Indicators: {Object.entries(collectionResult.extractions).map(([k, v]) => `${k}: ${v}`).join(' | ')}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Upload Card */}
        <div style={{ background: '#0d1524', border: '1px solid #1c2d4a', borderRadius: '8px', padding: '18px' }}>
          <h3 style={{ fontSize: '15px', color: '#f0f6fc', marginBottom: '8px' }}>Manual Threat Intelligence Upload</h3>
          <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '14px' }}>
            Upload raw JSON, JSONL, CSV, STIX 2.x, or plain-text threat observation dumps.
          </p>

          <form onSubmit={handleUpload}>
            <input
              type="file"
              onChange={e => setFile(e.target.files?.[0] || null)}
              accept=".json,.jsonl,.csv,.txt"
              style={{ display: 'block', marginBottom: '12px', fontSize: '12px', color: '#94a3b8' }}
            />
            <button
              type="submit"
              disabled={uploading || !file}
              style={{
                background: '#152238',
                border: '1px solid #00e5ff',
                color: '#00e5ff',
                padding: '8px 16px',
                borderRadius: '4px',
                fontWeight: 600,
                fontSize: '12px',
                cursor: uploading ? 'not-allowed' : 'pointer',
              }}
            >
              {uploading ? 'Parsing & Extracting...' : 'Upload & Correlate'}
            </button>
          </form>

          {error && <div style={{ color: '#ef4444', fontSize: '12px', marginTop: '10px' }}>{error}</div>}

          {uploadResult && (
            <div style={{ marginTop: '14px', background: '#090e17', padding: '12px', borderRadius: '6px', border: '1px solid #1c2d4a', fontSize: '12px' }}>
              <div style={{ color: '#10b981', fontWeight: 600, marginBottom: '4px' }}>Batch {uploadResult.batch_id} Processed</div>
              <div style={{ color: '#94a3b8' }}>Total: {uploadResult.total_records} | Accepted: {uploadResult.accepted} | Rejected: {uploadResult.rejected?.length || 0}</div>
            </div>
          )}
        </div>

        {/* SIEM Export Card */}
        <div style={{ background: '#0d1524', border: '1px solid #1c2d4a', borderRadius: '8px', padding: '18px' }}>
          <h3 style={{ fontSize: '15px', color: '#f0f6fc', marginBottom: '8px' }}>SIEM & EDR Export</h3>
          <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '14px' }}>
            Download verified indicators and provenance records in industry standard formats.
          </p>
          <div style={{ display: 'flex', gap: '10px' }}>
            <a
              href="/api/v1/export/indicators/json"
              target="_blank"
              style={{ textDecoration: 'none', background: '#152238', border: '1px solid #1c2d4a', color: '#00e5ff', padding: '8px 14px', borderRadius: '4px', fontSize: '12px', fontWeight: 600 }}
            >
              JSON Export
            </a>
            <a
              href="/api/v1/export/indicators/csv"
              target="_blank"
              style={{ textDecoration: 'none', background: '#152238', border: '1px solid #1c2d4a', color: '#00e5ff', padding: '8px 14px', borderRadius: '4px', fontSize: '12px', fontWeight: 600 }}
            >
              CSV Export
            </a>
            <a
              href="/api/v1/export/stix"
              target="_blank"
              style={{ textDecoration: 'none', background: '#152238', border: '1px solid #1c2d4a', color: '#00e5ff', padding: '8px 14px', borderRadius: '4px', fontSize: '12px', fontWeight: 600 }}
            >
              STIX 2.1 Bundle
            </a>
          </div>
        </div>
      </div>


      {/* Right: CERT-In Incident Draft Workflow */}
      <div style={{ background: '#0d1524', border: '1px solid #1c2d4a', borderRadius: '8px', padding: '20px', display: 'flex', flexDirection: 'column' }}>
        <h3 style={{ fontSize: '15px', color: '#f0f6fc', marginBottom: '4px' }}>CERT-In Preliminary Incident Report Draft</h3>
        <p style={{ fontSize: '11px', color: '#94a3b8', marginBottom: '14px' }}>
          Prepare preliminary incident drafts per statutory requirements under Section 70B of the IT Act (6-hour notification mandate).
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '10px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>Incident Title</label>
            <input
              type="text"
              value={certTitle}
              onChange={e => setCertTitle(e.target.value)}
              style={{ width: '100%', background: '#090e17', border: '1px solid #1c2d4a', padding: '6px 10px', borderRadius: '4px', color: '#f0f6fc', fontSize: '12px' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>Incident Category</label>
            <input
              type="text"
              value={certCategory}
              onChange={e => setCertCategory(e.target.value)}
              style={{ width: '100%', background: '#090e17', border: '1px solid #1c2d4a', padding: '6px 10px', borderRadius: '4px', color: '#f0f6fc', fontSize: '12px' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>Preliminary Severity</label>
            <select
              value={certSeverity}
              onChange={e => setCertSeverity(e.target.value)}
              style={{ width: '100%', background: '#090e17', border: '1px solid #1c2d4a', padding: '6px 10px', borderRadius: '4px', color: '#f0f6fc', fontSize: '12px' }}
            >
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
            </select>
          </div>
        </div>

        <div style={{ marginBottom: '12px' }}>
          <label style={{ display: 'block', fontSize: '11px', color: '#94a3b8', marginBottom: '4px' }}>Incident Summary</label>
          <textarea
            rows={3}
            value={certSummary}
            onChange={e => setCertSummary(e.target.value)}
            style={{ width: '100%', background: '#090e17', border: '1px solid #1c2d4a', padding: '8px', borderRadius: '4px', color: '#f0f6fc', fontSize: '12px' }}
          />
        </div>

        <button
          onClick={handleGenerateCertReport}
          style={{
            alignSelf: 'flex-start',
            background: '#00e5ff',
            color: '#080c14',
            padding: '6px 14px',
            borderRadius: '4px',
            fontWeight: 600,
            fontSize: '12px',
            marginBottom: '14px',
          }}
        >
          Generate Report Draft
        </button>

        {certReport && (
          <div style={{ flex: 1, overflowY: 'auto', background: '#090e17', border: '1px solid #1c2d4a', borderRadius: '6px', padding: '12px', fontSize: '11px', fontFamily: 'monospace', color: '#94a3b8' }}>
            <div style={{ color: '#f59e0b', fontWeight: 600, marginBottom: '6px' }}>{certReport.report_metadata?.status}</div>
            <div style={{ color: '#f0f6fc', marginBottom: '8px' }}>{certReport.report_metadata?.statutory_notice}</div>
            <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(certReport, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  );
};
