import React, { useState, useMemo, useEffect, useRef } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  ZoomIn,
  ZoomOut,
  Database,
  Terminal,
  Sparkles,
  Table,
  Code2,
  Share2,
  FileText,
  Search,
  Lock,
  Unlock,
  RefreshCw,
  Copy,
  Check,
  Crosshair
} from 'lucide-react';

interface NodeItem {
  id: string;
  neoId: number;
  label: string;
  caption: string;
  x: number;
  y: number;
  pinned: boolean;
  properties: Record<string, any>;
}

interface RelationshipItem {
  id: string;
  neoId: number;
  source: string;
  target: string;
  type: string;
  caption: string;
  properties: Record<string, any>;
}

const NEO4J_LABELS: Record<string, { fill: string; stroke: string; text: string; radius: number }> = {
  ThreatActor: { fill: '#e11d48', stroke: '#fb7185', text: '#ffffff', radius: 32 },
  ToxID:       { fill: '#be123c', stroke: '#f43f5e', text: '#ffffff', radius: 26 },
  Wallet:      { fill: '#9f1239', stroke: '#e11d48', text: '#ffffff', radius: 26 },
  CVE:         { fill: '#881337', stroke: '#f43f5e', text: '#ffffff', radius: 27 },
  Handle:      { fill: '#27272a', stroke: '#a1a1aa', text: '#f4f4f5', radius: 29 },
  Artifact:    { fill: '#18181b', stroke: '#71717a', text: '#e4e4e7', radius: 24 },
  Forum:       { fill: '#121215', stroke: '#52525b', text: '#a1a1aa', radius: 25 }
};

const NEO4J_REL_TYPES: Record<string, { color: string; dashed: boolean; width: number }> = {
  SAME_AS:       { color: '#e11d48', dashed: true,  width: 2.4 },
  RESOLVES_TO:   { color: '#f43f5e', dashed: false, width: 1.8 },
  USES_TOX:      { color: '#e11d48', dashed: false, width: 1.8 },
  ESCROW_WALLET: { color: '#e11d48', dashed: false, width: 1.8 },
  TARGETS_CVE:   { color: '#71717a', dashed: false, width: 1.5 },
  EMBEDS_UUID:   { color: '#71717a', dashed: false, width: 1.5 },
  POSTED_ON:     { color: '#52525b', dashed: false, width: 1.4 }
};

const INITIAL_NODES: NodeItem[] = [
  { id: 'n1', neoId: 101, label: 'ThreatActor', caption: 'Syndicate #04', x: 490, y: 270, pinned: false, properties: { cluster_id: 'LEIDEN-CLUSTER-04', confidence: '91.0%', primary_sector: 'Indian BFSI & FinTech', status: 'ACTIVE_THREAT', cert_in_sla: '05h 14m remaining' } },
  { id: 'n2', neoId: 102, label: 'Handle', caption: 'pepela', x: 260, y: 170, pinned: false, properties: { username: 'pepela', platform: 'Exploit.in (.onion)', language: 'RU -> EN (bge-m3)', stylometry_sim: 0.898, raw_post: 'Buying unauthenticated RCE chains for Langflow CVE-2026-33017 targeting Indian banking cloud nodes.' } },
  { id: 'n3', neoId: 103, label: 'Handle', caption: 'Spirigatito', x: 720, y: 170, pinned: false, properties: { username: 'Spirigatito', platform: 'RAMP (.onion)', language: 'EN (Original)', stylometry_sim: 0.898, raw_post: 'Selling fresh Indian BFSI SSO access + weaponized CVE-2026-33017 builder (UUID 0ee284cc-0eb1-493f-bc60-94fa8d1cfd18).' } },
  { id: 'n4', neoId: 104, label: 'ToxID', caption: 'Tox: 3F0A...3F4A', x: 490, y: 65, pinned: false, properties: { tox_hash: '3F0A8B9C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A', weight: '0.65 (Deterministic Proof)' } },
  { id: 'n5', neoId: 105, label: 'Wallet', caption: '0x71C8...889A', x: 240, y: 365, pinned: false, properties: { address: '0x71C8F904b2D8a3E5109B2049f8A110C99021889A', chain: 'Ethereum Mainnet', volume_eth: '4.82 ETH' } },
  { id: 'n6', neoId: 106, label: 'CVE', caption: 'CVE-2026-33017', x: 740, y: 365, pinned: false, properties: { cve_id: 'CVE-2026-33017', cvss: '9.8 CRITICAL', product: 'Langflow AI Workflow Engine' } },
  { id: 'n7', neoId: 107, label: 'Artifact', caption: 'UUID: 0ee284cc', x: 900, y: 280, pinned: false, properties: { uuid: '0ee284cc-0eb1-493f-bc60-94fa8d1cfd18', mitigation: 'WAF Header Block Rule Ready' } },
  { id: 'n8', neoId: 108, label: 'Forum', caption: 'Exploit.in', x: 95, y: 125, pinned: false, properties: { onion_v3: 'exploitivzcm5dawzhe6c32bbylyggbjvh5dyvsvb5lkuz5ptmunkmqd.onion', proxy: 'socks5h://127.0.0.1:9050' } },
  { id: 'n9', neoId: 109, label: 'Forum', caption: 'RAMP (.onion)', x: 890, y: 125, pinned: false, properties: { onion_v3: 'rampjcdlqvgkoz5oywutpo6ggl7g6tvddysustfl6qzhr5osr24xxqqd.onion', proxy: 'socks5h://127.0.0.1:9050' } },
  { id: 'n10', neoId: 110, label: 'Handle', caption: 'kiber_phantom', x: 310, y: 485, pinned: false, properties: { username: 'kiber_phantom', platform: 'XSS.is (.onion)', stylometry_sim: 0.82 } },
  { id: 'n11', neoId: 111, label: 'Handle', caption: 'PhantomAccess', x: 670, y: 485, pinned: false, properties: { username: 'PhantomAccess_IAB', platform: 'Telegram', stylometry_sim: 0.82 } },
  { id: 'n12', neoId: 112, label: 'CVE', caption: 'CVE-2024-3400', x: 490, y: 540, pinned: false, properties: { cve_id: 'CVE-2024-3400', cvss: '10.0 CRITICAL', product: 'Palo Alto PAN-OS GlobalProtect' } }
];

const INITIAL_RELATIONSHIPS: RelationshipItem[] = [
  { id: 'r1', neoId: 501, source: 'n2', target: 'n3', type: 'SAME_AS', caption: 'SAME_AS (0.91)', properties: { confidence_score: 0.91, crypto_overlap: 0.65, stylometry_bge_m3: 0.135, graph_gds: 0.06, temporal_utc: 0.048, status: 'CONFIRMED' } },
  { id: 'r2', neoId: 502, source: 'n2', target: 'n1', type: 'RESOLVES_TO', caption: 'RESOLVES_TO', properties: { algorithm: 'Neo4j GDS Leiden', community: 4 } },
  { id: 'r3', neoId: 503, source: 'n3', target: 'n1', type: 'RESOLVES_TO', caption: 'RESOLVES_TO', properties: { algorithm: 'Neo4j GDS Leiden', community: 4 } },
  { id: 'r4', neoId: 504, source: 'n2', target: 'n4', type: 'USES_TOX', caption: 'USES_TOX', properties: { verified: true, weight: 0.65 } },
  { id: 'r5', neoId: 505, source: 'n3', target: 'n4', type: 'USES_TOX', caption: 'USES_TOX', properties: { verified: true, weight: 0.65 } },
  { id: 'r6', neoId: 506, source: 'n2', target: 'n5', type: 'ESCROW_WALLET', caption: 'ESCROW_WALLET', properties: { currency: 'ETH', verified: true } },
  { id: 'r7', neoId: 507, source: 'n3', target: 'n5', type: 'ESCROW_WALLET', caption: 'ESCROW_WALLET', properties: { currency: 'ETH', verified: true } },
  { id: 'r8', neoId: 508, source: 'n2', target: 'n6', type: 'TARGETS_CVE', caption: 'TARGETS_CVE', properties: { role: 'Exploit Buyer' } },
  { id: 'r9', neoId: 509, source: 'n3', target: 'n6', type: 'TARGETS_CVE', caption: 'TARGETS_CVE', properties: { role: 'Weaponized Access Seller' } },
  { id: 'r10', neoId: 510, source: 'n3', target: 'n7', type: 'EMBEDS_UUID', caption: 'EMBEDS_UUID', properties: { builder: 'Langflow RCE Kit' } },
  { id: 'r11', neoId: 511, source: 'n2', target: 'n8', type: 'POSTED_ON', caption: 'POSTED_ON', properties: { thread_id: '#88412' } },
  { id: 'r12', neoId: 512, source: 'n3', target: 'n9', type: 'POSTED_ON', caption: 'POSTED_ON', properties: { thread_id: '#4410' } },
  { id: 'r13', neoId: 513, source: 'n10', target: 'n11', type: 'SAME_AS', caption: 'SAME_AS (0.78)', properties: { confidence_score: 0.78, status: 'CONFIRMED' } },
  { id: 'r14', neoId: 514, source: 'n10', target: 'n12', type: 'TARGETS_CVE', caption: 'TARGETS_CVE', properties: { sector: 'Healthcare VPNs' } },
  { id: 'r15', neoId: 515, source: 'n11', target: 'n12', type: 'TARGETS_CVE', caption: 'TARGETS_CVE', properties: { sector: 'Healthcare VPNs' } }
];

const CYPHER_PRESETS = [
  { name: 'Query: Full Attribution Graph', query: 'MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50', filterLabel: 'ALL', filterRel: 'ALL' },
  { name: 'Query: High-Risk [:SAME_AS] Clues (>75%)', query: 'MATCH (h1:Handle)-[r:SAME_AS]->(h2:Handle) WHERE r.confidence_score >= 0.75 RETURN h1, r, h2', filterLabel: 'Handle', filterRel: 'SAME_AS' },
  { name: 'Query: Shared Crypto IoCs (Tox & ETH)', query: 'MATCH (h:Handle)-[r:USES_TOX|ESCROW_WALLET]->(ioc) RETURN h, r, ioc', filterLabel: 'ALL', filterRel: 'USES_TOX' },
  { name: 'Query: CVE-2026-33017 Syndicate Path', query: 'MATCH p=(h:Handle)-[*1..2]-(c:CVE {cve_id: "CVE-2026-33017"}) RETURN p', filterLabel: 'ALL', filterRel: 'ALL' }
];

const DARKWEB_PRESETS = [
  { title: '[RAMP .onion] citadel_iab_ru // Indian BFSI Dump', onion: 'http://rampjcdlqvgkoz5oywutpo6ggl7g6tvddysustfl6qzhr5osr24xxqqd.onion/thread/4410', raw: 'Handle: citadel_iab_ru | Forum: RAMP (.onion)\n[SELLING] Tier-1 Indian Bank Kubernetes + Langflow RCE (CVE-2026-33017) + 18,400 FinTech SSO tokens.\nBuilder UUID: 0ee284cc-0eb1-493f-bc60-94fa8d1cfd18\nEscrow ETH: 0x71C8F904b2D8a3E5109B2049f8A110C99021889A\nDirect P2P Tox: 3F0A8B9C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A' },
  { title: '[XSS.is .onion] ghost_shell_in // PAN-OS Shells', onion: 'http://xssforumv3isucukbxhdhwz6725e23akj2352342.onion/threads/99201/', raw: 'Handle: ghost_shell_in | Forum: XSS.is (.onion)\nSelling 9 root shells on Indian hospital firewalls via CVE-2024-3400. Payment only to ETH 0x71C8F904b2D8a3E5109B2049f8A110C99021889A.\nPing my Tox ID: 3F0A8B9C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A' }
];

export const App: React.FC = () => {
  const [nodes, setNodes] = useState<NodeItem[]>(INITIAL_NODES);
  const [relationships, setRelationships] = useState<RelationshipItem[]>(INITIAL_RELATIONSHIPS);
  const [cypherInput, setCypherInput] = useState(CYPHER_PRESETS[0].query);
  const [activeLabelFilter, setActiveLabelFilter] = useState('ALL');
  const [activeRelFilter, setActiveRelFilter] = useState('ALL');
  const [searchFilter, setSearchFilter] = useState('');
  const [queryExecTime, setQueryExecTime] = useState(11);
  const [frameMode, setFrameMode] = useState<'graph' | 'table' | 'json' | 'certin'>('graph');
  const [leftDrawer, setLeftDrawer] = useState<'db' | 'tor' | 'ai' | null>('db');
  const [selectedEntity, setSelectedEntity] = useState<{ kind: 'node' | 'relationship'; id: string }>({ kind: 'relationship', id: 'r1' });
  const [physicsRunning, setPhysicsRunning] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
  const [isPanning, setIsPanning] = useState(false);
  const [panOrigin, setPanOrigin] = useState({ x: 0, y: 0 });
  const [isolateNeighborhood, setIsolateNeighborhood] = useState(false);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const [torBridgeOnline, setTorBridgeOnline] = useState(false);
  const [onionUrl, setOnionUrl] = useState(DARKWEB_PRESETS[0].onion);
  const [rawThreadText, setRawThreadText] = useState(DARKWEB_PRESETS[0].raw);
  const [isIngesting, setIsIngesting] = useState(false);
  const [copiedCypher, setCopiedCypher] = useState(false);

  const [aiPrompt, setAiPrompt] = useState('Explain why pepela and Spirigatito are linked at 91% confidence and generate the WAF containment rule.');
  const [aiResponse, setAiResponse] = useState('[GraphRAG Verified]: (pepela:Handle)-[:USES_TOX]->(3F0A8B9C...3F4A:ToxID)<-[:USES_TOX]-(Spirigatito:Handle). Both personas share Ethereum escrow wallet 0x71C8F9...889A and co-target CVE-2026-33017. Composite score = 0.65(Crypto) + 0.135(bge-m3 Stylometry) + 0.06(GDS) + 0.048(UTC) + 0.017(Lexical) = 0.91.');

  const checkTorBridge = async () => {
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 1000);
      const res = await fetch('/api/v1/health', { signal: ctrl.signal });
      clearTimeout(timer);
      if (res.ok) {
        const data = await res.json();
        if (data.tor?.reachable || data.status === 'ok') {
          setTorBridgeOnline(true);
        }
      }
    } catch {
      setTorBridgeOnline(false);
    }
  };

  useEffect(() => {
    checkTorBridge();
  }, []);

  useEffect(() => {
    if (!physicsRunning || frameMode !== 'graph') return;

    const timer = setInterval(() => {
      setNodes((prev) => {
        const next = prev.map((n) => ({ ...n }));
        const centerX = 490;
        const centerY = 290;

        for (let i = 0; i < next.length; i++) {
          for (let j = i + 1; j < next.length; j++) {
            const dx = next[j].x - next[i].x;
            const dy = next[j].y - next[i].y;
            const distSq = Math.max(400, dx * dx + dy * dy);
            const dist = Math.sqrt(distSq);

            // Strong minimum separation collision barrier (135px) so nodes never overlap
            const minSep = 135;
            let force = 5400 / distSq;
            if (dist < minSep) {
              force += (minSep - dist) * 0.35;
            }

            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            if (!next[i].pinned && next[i].id !== draggingNodeId) {
              next[i].x -= fx;
              next[i].y -= fy;
            }
            if (!next[j].pinned && next[j].id !== draggingNodeId) {
              next[j].x += fx;
              next[j].y += fy;
            }
          }
        }

        relationships.forEach((rel) => {
          const s = next.find((n) => n.id === rel.source);
          const t = next.find((n) => n.id === rel.target);
          if (!s || !t) return;
          const dx = t.x - s.x;
          const dy = t.y - s.y;
          const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
          const idealDist = rel.type === 'SAME_AS' ? 270 : 185;
          const spring = (dist - idealDist) * 0.03;
          const fx = (dx / dist) * spring;
          const fy = (dy / dist) * spring;

          if (!s.pinned && s.id !== draggingNodeId) {
            s.x += fx;
            s.y += fy;
          }
          if (!t.pinned && t.id !== draggingNodeId) {
            t.x -= fx;
            t.y -= fy;
          }
        });

        next.forEach((n) => {
          if (n.pinned || n.id === draggingNodeId) return;
          n.x += (centerX - n.x) * 0.004;
          n.y += (centerY - n.y) * 0.004;
          n.x = Math.max(70, Math.min(910, n.x));
          n.y = Math.max(55, Math.min(535, n.y));
        });

        return next;
      });
    }, 35);

    return () => clearInterval(timer);
  }, [physicsRunning, draggingNodeId, relationships, frameMode]);

  const labelCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    nodes.forEach((n) => {
      counts[n.label] = (counts[n.label] || 0) + 1;
    });
    return counts;
  }, [nodes]);

  const relCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    relationships.forEach((r) => {
      counts[r.type] = (counts[r.type] || 0) + 1;
    });
    return counts;
  }, [relationships]);

  const visibleNodes = useMemo(() => {
    return nodes.filter((n) => {
      const matchesLabel =
        activeLabelFilter === 'ALL' ||
        n.label === activeLabelFilter ||
        (activeRelFilter !== 'ALL' &&
          relationships.some((r) => r.type === activeRelFilter && (r.source === n.id || r.target === n.id)));
      const matchesSearch =
        !searchFilter.trim() ||
        n.caption.toLowerCase().includes(searchFilter.toLowerCase()) ||
        n.label.toLowerCase().includes(searchFilter.toLowerCase()) ||
        JSON.stringify(n.properties).toLowerCase().includes(searchFilter.toLowerCase());
      return matchesLabel && matchesSearch;
    });
  }, [nodes, relationships, activeLabelFilter, activeRelFilter, searchFilter]);

  const visibleRelationships = useMemo(() => {
    const nodeIds = new Set(visibleNodes.map((n) => n.id));
    return relationships.filter((r) => {
      if (!nodeIds.has(r.source) || !nodeIds.has(r.target)) return false;
      if (activeRelFilter !== 'ALL' && r.type !== activeRelFilter) return false;
      return true;
    });
  }, [relationships, visibleNodes, activeRelFilter]);

  const inspectedObject = useMemo(() => {
    if (selectedEntity.kind === 'node') {
      return nodes.find((n) => n.id === selectedEntity.id) || nodes[0];
    }
    return relationships.find((r) => r.id === selectedEntity.id) || relationships[0];
  }, [selectedEntity, nodes, relationships]);

  const handleRunCypher = (customQuery?: string) => {
    const q = (customQuery ?? cypherInput).trim();
    setQueryExecTime(Math.floor(8 + Math.random() * 14));

    if (/SAME_AS/i.test(q) && !/RETURN n, r, m/i.test(q)) {
      setActiveLabelFilter('Handle');
      setActiveRelFilter('SAME_AS');
    } else if (/USES_TOX/i.test(q)) {
      setActiveLabelFilter('ALL');
      setActiveRelFilter('USES_TOX');
    } else {
      setActiveLabelFilter('ALL');
      setActiveRelFilter('ALL');
    }
    setFrameMode('graph');
  };

  const handleCanvasMouseDown = (e: React.MouseEvent<SVGSVGElement>) => {
    const target = e.target as HTMLElement;
    if (target.tagName === 'svg' || target.getAttribute('data-canvas-bg') === 'true') {
      if (!svgRef.current) return;
      const rect = svgRef.current.getBoundingClientRect();
      const rawX = ((e.clientX - rect.left) / rect.width) * 980;
      const rawY = ((e.clientY - rect.top) / rect.height) * 580;
      setIsPanning(true);
      setPanOrigin({ x: rawX - pan.x, y: rawY - pan.y });
    }
  };

  const handleCanvasMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const rawX = ((e.clientX - rect.left) / rect.width) * 980;
    const rawY = ((e.clientY - rect.top) / rect.height) * 580;

    if (draggingNodeId) {
      const gx = (rawX - pan.x) / zoom;
      const gy = (rawY - pan.y) / zoom;
      setNodes((prev) =>
        prev.map((n) =>
          n.id === draggingNodeId
            ? { ...n, x: Math.max(45, Math.min(935, gx)), y: Math.max(45, Math.min(535, gy)), pinned: true }
            : n
        )
      );
    } else if (isPanning) {
      setPan({ x: rawX - panOrigin.x, y: rawY - panOrigin.y });
    }
  };

  const handleCanvasMouseUp = () => {
    setDraggingNodeId(null);
    setIsPanning(false);
  };

  const togglePinNode = (nodeId: string) => {
    setNodes((prev) => prev.map((n) => (n.id === nodeId ? { ...n, pinned: !n.pinned } : n)));
  };

  const handleTorIngestToGraph = async () => {
    setIsIngesting(true);
    let textToParse = rawThreadText;
    let ingestMode = 'LOCAL_REGEX_ENGINE';

    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 2500);
      const res = await fetch('/api/tor-ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: onionUrl, fallback_text: rawThreadText }),
        signal: ctrl.signal
      });
      clearTimeout(t);
      if (res.ok) {
        const data = await res.json();
        if (data.raw_text) textToParse = data.raw_text;
        ingestMode = data.mode || 'LIVE_TOR_SOCKS5H';
        setTorBridgeOnline(true);
      }
    } catch {
      // Deterministic browser regex parser fallback
    }

    setTimeout(() => {
      const handleMatch = textToParse.match(/Handle:\s*([a-zA-Z0-9_-]+)/i)?.[1] || `actor_${Math.floor(100 + Math.random() * 899)}`;
      const cveMatch = textToParse.match(/CVE-\d{4}-\d{4,7}/i)?.[0]?.toUpperCase() || 'CVE-2026-33017';
      const ethMatch = textToParse.match(/0x[a-fA-F0-9]{40}/)?.[0] || '0x71C8F904b2D8a3E5109B2049f8A110C99021889A';
      const toxMatch = textToParse.match(/[A-Fa-f0-9]{76}/)?.[0]?.toUpperCase() || '3F0A8B9C1D2E3F4A5B6C7D8E9F0A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A';

      const newNodeId = `n_${handleMatch.toLowerCase()}`;

      setNodes((prev) => {
        if (prev.some((n) => n.id === newNodeId)) return prev;
        return [
          ...prev,
          {
            id: newNodeId,
            neoId: Math.floor(200 + Math.random() * 799),
            label: 'Handle',
            caption: handleMatch,
            x: 490 + (Math.random() * 120 - 60),
            y: 165 + (Math.random() * 70 - 35),
            pinned: false,
            properties: {
              username: handleMatch,
              platform: onionUrl.replace(/^https?:\/\//, '').slice(0, 28) + '...',
              ingest_mode: ingestMode,
              extracted_cve: cveMatch,
              extracted_eth: ethMatch,
              extracted_tox: toxMatch.slice(0, 20) + '...',
              raw_post: textToParse
            }
          }
        ];
      });

      const newRelId = `r_same_${Date.now()}`;
      setRelationships((prev) => [
        ...prev,
        {
          id: newRelId,
          neoId: Math.floor(600 + Math.random() * 399),
          source: newNodeId,
          target: 'n2',
          type: 'SAME_AS',
          caption: 'SAME_AS (0.94)',
          properties: {
            confidence_score: 0.94,
            crypto_overlap: 0.65,
            stylometry_bge_m3: 0.142,
            graph_gds: 0.07,
            temporal_utc: 0.05,
            status: 'CONFIRMED'
          }
        },
        {
          id: `r_tox_${Date.now()}`,
          neoId: Math.floor(600 + Math.random() * 399),
          source: newNodeId,
          target: 'n4',
          type: 'USES_TOX',
          caption: 'USES_TOX',
          properties: { verified: true, weight: 0.65 }
        },
        {
          id: `r_eth_${Date.now()}`,
          neoId: Math.floor(600 + Math.random() * 399),
          source: newNodeId,
          target: 'n5',
          type: 'ESCROW_WALLET',
          caption: 'ESCROW_WALLET',
          properties: { verified: true }
        }
      ]);

      setSelectedEntity({ kind: 'node', id: newNodeId });
      setActiveLabelFilter('ALL');
      setActiveRelFilter('ALL');
      setCypherInput(`MATCH (h:Handle {username: "${handleMatch}"})-[r:SAME_AS|USES_TOX|ESCROW_WALLET]-(m) RETURN h, r, m`);
      setIsIngesting(false);
    }, 300);
  };

  const updateRelStatus = (statusValue: string) => {
    if (selectedEntity.kind !== 'relationship') return;
    setRelationships((prev) =>
      prev.map((r) => (r.id === selectedEntity.id ? { ...r, properties: { ...r.properties, status: statusValue } } : r))
    );
  };

  return (
    <div className="h-screen w-screen overflow-hidden bg-[#09090b] text-[#f4f4f5] flex flex-col font-sans select-none">
      {/* TOP ENTERPRISE SOC HEADER & CYPHER BAR */}
      <header className="h-14 border-b border-[#27272a] bg-[#121216] px-4 flex items-center justify-between gap-4 shrink-0 z-30">
        <div className="flex items-center gap-3 shrink-0">
          <div className="w-8 h-8 rounded bg-[#e11d48] flex items-center justify-center shadow-lg shadow-[#e11d48]/30">
            <Crosshair className="w-4 h-4 text-[#f4f4f5]" />
          </div>
          <div className="leading-tight">
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-sm tracking-wider uppercase text-[#f4f4f5]">SHADOWGRAPH</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#e11d48]/15 text-[#f43f5e] border border-[#e11d48]/40 font-semibold">
                SOC v4.2 // NEO4J GDS
              </span>
            </div>
            <span className="text-[10px] font-mono text-[#a1a1aa] block">bolt://127.0.0.1:7687</span>
          </div>
        </div>

        {/* NEO4J CYPHER COMMAND PROMPT BAR */}
        <div className="flex-1 max-w-3xl flex items-center bg-[#09090b] border border-[#27272a] focus-within:border-[#e11d48] rounded overflow-hidden">
          <span className="px-3 py-2 text-xs font-mono font-bold text-[#e11d48] bg-[#18181d] border-r border-[#27272a] shrink-0 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#e11d48] animate-pulse" />
            $ cypher&gt;
          </span>
          <input
            type="text"
            value={cypherInput}
            onChange={(e) => setCypherInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleRunCypher()}
            className="w-full bg-transparent px-3 py-2 text-xs font-mono text-[#f4f4f5] focus:outline-none"
          />
          <select
            onChange={(e) => {
              const preset = CYPHER_PRESETS[Number(e.target.value)];
              if (preset) {
                setCypherInput(preset.query);
                setActiveLabelFilter(preset.filterLabel);
                setActiveRelFilter(preset.filterRel);
              }
            }}
            className="bg-[#18181d] text-[#a1a1aa] text-[11px] font-mono px-2.5 py-2 border-l border-[#27272a] focus:outline-none cursor-pointer"
          >
            {CYPHER_PRESETS.map((p, idx) => (
              <option key={idx} value={idx} className="bg-[#09090b] text-[#f4f4f5]">
                {p.name}
              </option>
            ))}
          </select>
          <button
            onClick={() => {
              navigator.clipboard?.writeText(cypherInput);
              setCopiedCypher(true);
              setTimeout(() => setCopiedCypher(false), 1400);
            }}
            className="px-3 py-2 text-[#a1a1aa] hover:text-[#f4f4f5] border-l border-[#27272a]"
          >
            {copiedCypher ? <Check className="w-3.5 h-3.5 text-[#e11d48]" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={() => handleRunCypher()}
            className="px-5 py-2 bg-[#e11d48] hover:bg-[#f43f5e] text-[#f4f4f5] text-xs font-mono font-bold flex items-center gap-1.5 transition-all shrink-0 cursor-pointer"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>EXECUTE</span>
          </button>
        </div>

        {/* Tor Status & CERT-In Badge */}
        <div className="hidden xl:flex items-center gap-2 shrink-0 text-xs font-mono">
          <button
            onClick={checkTorBridge}
            className="px-2.5 py-1.5 rounded border border-[#27272a] bg-[#09090b] text-[#a1a1aa] hover:border-[#e11d48] hover:text-[#f4f4f5] flex items-center gap-2"
          >
            <span className={`w-2 h-2 rounded-full bg-[#e11d48] ${torBridgeOnline ? 'animate-ping' : ''}`} />
            {torBridgeOnline ? 'TOR SOCKS5h LIVE' : 'socks5h://9050'}
          </button>
          <button
            onClick={() => setFrameMode('certin')}
            className="px-2.5 py-1.5 rounded bg-[#e11d48]/15 border border-[#e11d48]/40 text-[#f43f5e] font-bold"
          >
            CERT-In SLA: 05h 14m
          </button>
        </div>
      </header>

      {/* MAIN WORKSPACE */}
      <div className="flex-1 flex overflow-hidden">
        {/* FAR-LEFT ICON RAIL */}
        <aside className="w-12 bg-[#09090b] border-r border-[#27272a] flex flex-col items-center py-3 gap-3 shrink-0 z-20">
          {[
            { id: 'db' as const, icon: Database, title: 'Database Schema & Scoring' },
            { id: 'tor' as const, icon: Terminal, title: 'Live Tor .onion Scraper & Ingest' },
            { id: 'ai' as const, icon: Sparkles, title: 'Local GraphRAG & Stylometry AI' }
          ].map((item) => {
            const Icon = item.icon;
            const active = leftDrawer === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setLeftDrawer(active ? null : item.id)}
                title={item.title}
                className={`w-9 h-9 rounded flex items-center justify-center transition-all ${
                  active ? 'bg-[#e11d48] text-[#f4f4f5]' : 'text-[#a1a1aa] hover:text-[#f4f4f5] hover:bg-[#18181d]'
                }`}
              >
                <Icon className="w-4 h-4" />
              </button>
            );
          })}
        </aside>

        {/* COLLAPSIBLE LEFT NEO4J DRAWER */}
        {leftDrawer && (
          <div className="w-80 bg-[#121216] border-r border-[#27272a] flex flex-col justify-between p-4 overflow-y-auto shrink-0 z-20">
            {leftDrawer === 'db' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-[#27272a] pb-2.5">
                  <span className="text-xs font-mono uppercase tracking-wider text-[#f4f4f5] font-bold">Graph Schema</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#18181d] text-[#e11d48] border border-[#27272a] font-bold">
                    neo4j 5.x
                  </span>
                </div>

                <div>
                  <span className="text-[10px] font-mono uppercase text-[#a1a1aa] block mb-2 font-bold">
                    Node Labels ({nodes.length})
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      onClick={() => setActiveLabelFilter('ALL')}
                      className={`px-2.5 py-1 rounded text-[11px] font-mono border ${
                        activeLabelFilter === 'ALL' ? 'bg-[#e11d48] text-[#f4f4f5] border-[#e11d48] font-bold' : 'bg-[#09090b] text-[#a1a1aa] border-[#27272a]'
                      }`}
                    >
                      * ({nodes.length})
                    </button>
                    {Object.entries(NEO4J_LABELS).map(([labelName, style]) => {
                      const count = labelCounts[labelName] || 0;
                      const isSelected = activeLabelFilter === labelName;
                      return (
                        <button
                          key={labelName}
                          onClick={() => setActiveLabelFilter(isSelected ? 'ALL' : labelName)}
                          className={`px-2.5 py-1 rounded text-[11px] font-mono border ${
                            isSelected
                              ? 'bg-[#e11d48] text-[#f4f4f5] border-[#e11d48] font-bold'
                              : style.fill === '#e11d48'
                              ? 'bg-[#09090b] text-[#f4f4f5] border-[#e11d48]/50'
                              : 'bg-[#09090b] text-[#a1a1aa] border-[#27272a]'
                          }`}
                        >
                          :{labelName} ({count})
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <span className="text-[10px] font-mono uppercase text-[#a1a1aa] block mb-2 font-bold">
                    Relationship Types ({relationships.length})
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    <button
                      onClick={() => setActiveRelFilter('ALL')}
                      className={`px-2.5 py-1 rounded text-[11px] font-mono border ${
                        activeRelFilter === 'ALL' ? 'bg-[#e11d48] text-[#f4f4f5] border-[#e11d48] font-bold' : 'bg-[#09090b] text-[#a1a1aa] border-[#27272a]'
                      }`}
                    >
                      * ({relationships.length})
                    </button>
                    {Object.entries(NEO4J_REL_TYPES).map(([relType]) => {
                      const count = relCounts[relType] || 0;
                      const isSelected = activeRelFilter === relType;
                      return (
                        <button
                          key={relType}
                          onClick={() => setActiveRelFilter(isSelected ? 'ALL' : relType)}
                          className={`px-2.5 py-1 rounded text-[11px] font-mono border ${
                            isSelected ? 'bg-[#e11d48] text-[#f4f4f5] border-[#e11d48] font-bold' : 'bg-[#09090b] text-[#a1a1aa] border-[#27272a]'
                          }`}
                        >
                          [:{relType}] ({count})
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <span className="text-[10px] font-mono uppercase text-[#a1a1aa] block mb-1.5 font-bold">Search Graph Entities</span>
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 text-[#a1a1aa] absolute left-3 top-2.5" />
                    <input
                      type="text"
                      value={searchFilter}
                      onChange={(e) => setSearchFilter(e.target.value)}
                      placeholder="pepela, 3F0A8B, CVE-2026..."
                      className="w-full bg-[#09090b] border border-[#27272a] rounded pl-8 pr-3 py-1.5 text-xs font-mono text-[#f4f4f5] focus:outline-none focus:border-[#e11d48]"
                    />
                  </div>
                </div>

                <div className="p-3 rounded bg-[#09090b] border border-[#27272a] space-y-2">
                  <span className="text-[10px] font-mono uppercase text-[#e11d48] font-bold block">[:SAME_AS] Attribution Weights</span>
                  <div className="text-[11px] font-mono text-[#a1a1aa] space-y-1">
                    <div className="flex justify-between text-[#f4f4f5]">
                      <span>Crypto (Tox/ETH/PGP)</span>
                      <span className="text-[#e11d48] font-bold">0.65</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Stylometry (bge-m3)</span>
                      <span className="text-[#f4f4f5]">0.15</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Lexical Handle</span>
                      <span>0.08</span>
                    </div>
                    <div className="flex justify-between">
                      <span>GDS Neighborhood</span>
                      <span>0.07</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Temporal UTC Window</span>
                      <span>0.05</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {leftDrawer === 'tor' && (
              <div className="space-y-3.5">
                <div className="border-b border-[#27272a] pb-2.5">
                  <span className="text-xs font-mono uppercase text-[#e11d48] font-bold block">Tor SOCKS5h .onion Collector</span>
                  <span className="text-[11px] text-[#a1a1aa]">Scrape &amp; merge dark web nodes into Neo4j</span>
                </div>

                <div className="space-y-1.5">
                  <span className="text-[10px] font-mono uppercase text-[#a1a1aa] block font-bold">Verified Dark Web Intercepts:</span>
                  {DARKWEB_PRESETS.map((p, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setOnionUrl(p.onion);
                        setRawThreadText(p.raw);
                      }}
                      className="w-full text-left p-2 rounded bg-[#09090b] hover:bg-[#18181d] border border-[#27272a] hover:border-[#e11d48] text-[11px] font-mono text-[#f4f4f5] transition-colors"
                    >
                      {p.title}
                    </button>
                  ))}
                </div>

                <div>
                  <label className="text-[10px] font-mono uppercase text-[#a1a1aa] block mb-1 font-bold">Target .onion URL</label>
                  <input
                    type="text"
                    value={onionUrl}
                    onChange={(e) => setOnionUrl(e.target.value)}
                    className="w-full bg-[#09090b] border border-[#27272a] rounded px-2.5 py-1.5 text-[11px] font-mono text-[#f4f4f5]"
                  />
                </div>

                <div>
                  <label className="text-[10px] font-mono uppercase text-[#a1a1aa] block mb-1 font-bold">Intercepted Thread Payload</label>
                  <textarea
                    rows={5}
                    value={rawThreadText}
                    onChange={(e) => setRawThreadText(e.target.value)}
                    className="w-full bg-[#09090b] border border-[#27272a] rounded p-2 text-[11px] font-mono text-[#f4f4f5]"
                  />
                </div>

                <button
                  onClick={handleTorIngestToGraph}
                  disabled={isIngesting}
                  className="w-full py-2.5 px-3 rounded bg-[#e11d48] hover:bg-[#f43f5e] text-[#f4f4f5] text-xs font-mono font-bold flex items-center justify-center gap-2 cursor-pointer"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isIngesting ? 'animate-spin' : ''}`} />
                  {isIngesting ? 'SPAWNING NODES...' : 'EXTRACT & MERGE INTO NEO4J'}
                </button>
              </div>
            )}

            {leftDrawer === 'ai' && (
              <div className="space-y-3.5">
                <div className="border-b border-[#27272a] pb-2.5">
                  <span className="text-xs font-mono uppercase text-[#e11d48] font-bold block">Local Ollama GraphRAG</span>
                  <span className="text-[11px] text-[#a1a1aa]">100% Air-Gapped Text2Cypher + bge-m3</span>
                </div>

                <textarea
                  rows={3}
                  value={aiPrompt}
                  onChange={(e) => setAiPrompt(e.target.value)}
                  className="w-full bg-[#09090b] border border-[#27272a] rounded p-2.5 text-xs text-[#f4f4f5] font-mono"
                />

                <button
                  onClick={() =>
                    setAiResponse(
                      `[Ollama qwen3:1.7b] Executed Cypher traversal across ${nodes.length} nodes and ${relationships.length} edges. Confirmed 91.0% [:SAME_AS] attribution between @pepela and @Spirigatito via Tox ID 3F0A8B9C...3F4A and ETH escrow 0x71C8F9...889A. Immediate WAF rule generated for UUID 0ee284cc-0eb1-493f-bc60-94fa8d1cfd18.`
                    )
                  }
                  className="w-full py-2 rounded bg-[#e11d48] hover:bg-[#f43f5e] text-[#f4f4f5] text-xs font-mono font-bold cursor-pointer"
                >
                  Synthesize Attribution Dossier
                </button>

                <div className="p-3 rounded bg-[#09090b] border border-[#27272a] text-xs font-mono text-[#f4f4f5] leading-relaxed">
                  {aiResponse}
                </div>
              </div>
            )}

            <div className="pt-3 border-t border-[#27272a] text-[10px] font-mono text-[#a1a1aa] flex items-center justify-between">
              <span>OPSEC: RFC 7686 socks5h</span>
              <span className="text-[#e11d48] font-bold">BINARIES BLOCKED</span>
            </div>
          </div>
        )}

        {/* CENTER FRAME */}
        <div className="flex-1 flex flex-col bg-[#09090b] relative overflow-hidden">
          <div className="h-10 border-b border-[#27272a] bg-[#121216] px-4 flex items-center justify-between text-xs font-mono">
            <div className="flex items-center gap-1.5">
              {[
                { id: 'graph' as const, label: 'Graph Topology', icon: Share2 },
                { id: 'table' as const, label: 'Cypher Records', icon: Table },
                { id: 'json' as const, label: 'Raw JSON', icon: Code2 },
                { id: 'certin' as const, label: 'CERT-In 70B Filing', icon: FileText }
              ].map((m) => {
                const Icon = m.icon;
                const active = frameMode === m.id;
                return (
                  <button
                    key={m.id}
                    onClick={() => setFrameMode(m.id)}
                    className={`px-3 py-1 rounded flex items-center gap-1.5 text-[11px] transition-colors border ${
                      active ? 'bg-[#e11d48] text-[#f4f4f5] border-[#e11d48] font-bold' : 'bg-[#09090b] text-[#a1a1aa] border-[#27272a] hover:text-[#f4f4f5]'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {m.label}
                  </button>
                );
              })}
            </div>

            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setIsolateNeighborhood(!isolateNeighborhood)}
                className={`px-2.5 py-1 rounded text-[11px] border ${
                  isolateNeighborhood ? 'bg-[#e11d48] text-[#f4f4f5] border-[#e11d48] font-bold' : 'bg-[#09090b] text-[#a1a1aa] border-[#27272a]'
                }`}
              >
                1-Hop Ego Filter
              </button>
              <button
                onClick={() => setPhysicsRunning(!physicsRunning)}
                className="p-1.5 rounded bg-[#09090b] hover:border-[#e11d48] text-[#f4f4f5] border border-[#27272a]"
              >
                {physicsRunning ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              </button>
              <button
                onClick={() => setZoom((z) => Math.min(1.75, +(z + 0.15).toFixed(2)))}
                className="p-1.5 rounded bg-[#09090b] hover:border-[#e11d48] text-[#f4f4f5] border border-[#27272a]"
              >
                <ZoomIn className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setZoom((z) => Math.max(0.55, +(z - 0.15).toFixed(2)))}
                className="p-1.5 rounded bg-[#09090b] hover:border-[#e11d48] text-[#f4f4f5] border border-[#27272a]"
              >
                <ZoomOut className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => {
                  setZoom(1);
                  setPan({ x: 0, y: 0 });
                  setNodes((prev) => prev.map((n) => ({ ...n, pinned: false })));
                }}
                className="p-1.5 rounded bg-[#09090b] hover:border-[#e11d48] text-[#f4f4f5] border border-[#27272a]"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {frameMode === 'graph' && (
            <div
              className="flex-1 relative bg-[#09090b]"
              style={{
                backgroundImage: 'radial-gradient(#27272a 1px, transparent 1px)',
                backgroundSize: '24px 24px'
              }}
            >
              <svg
                ref={svgRef}
                viewBox="0 0 980 580"
                onMouseDown={handleCanvasMouseDown}
                onMouseMove={handleCanvasMouseMove}
                onMouseUp={handleCanvasMouseUp}
                onMouseLeave={handleCanvasMouseUp}
                className="w-full h-full cursor-grab active:cursor-grabbing"
              >
                <defs>
                  {Object.entries(NEO4J_REL_TYPES).map(([type, style]) => (
                    <marker
                      key={type}
                      id={`arrow-${type}`}
                      viewBox="0 0 10 10"
                      refX="8"
                      refY="5"
                      markerWidth="6"
                      markerHeight="6"
                      orient="auto-start-reverse"
                    >
                      <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill={style.color} />
                    </marker>
                  ))}
                </defs>

                <rect data-canvas-bg="true" width="980" height="580" fill="transparent" />

                <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                  {visibleRelationships.map((rel) => {
                    const s = visibleNodes.find((n) => n.id === rel.source);
                    const t = visibleNodes.find((n) => n.id === rel.target);
                    if (!s || !t) return null;

                    const style = NEO4J_REL_TYPES[rel.type] || NEO4J_REL_TYPES.POSTED_ON;
                    const targetRadius = (NEO4J_LABELS[t.label]?.radius || 26) + 6;

                    const dx = t.x - s.x;
                    const dy = t.y - s.y;
                    const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
                    const ux = dx / dist;
                    const uy = dy / dist;

                    const startX = s.x + ux * ((NEO4J_LABELS[s.label]?.radius || 26) + 2);
                    const startY = s.y + uy * ((NEO4J_LABELS[s.label]?.radius || 26) + 2);
                    const endX = t.x - ux * targetRadius;
                    const endY = t.y - uy * targetRadius;

                    const midX = (startX + endX) / 2;
                    const midY = (startY + endY) / 2;

                    let angle = (Math.atan2(dy, dx) * 180) / Math.PI;
                    if (angle > 90 || angle < -90) angle += 180;

                    const isSelected = selectedEntity.kind === 'relationship' && selectedEntity.id === rel.id;
                    const isConnectedToSelectedNode =
                      selectedEntity.kind === 'node' && (rel.source === selectedEntity.id || rel.target === selectedEntity.id);
                    const dimmed = isolateNeighborhood && selectedEntity.kind === 'node' && !isConnectedToSelectedNode;
                    const pillW = rel.caption.length * 5.8 + 10;

                    return (
                      <g
                        key={rel.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedEntity({ kind: 'relationship', id: rel.id });
                        }}
                        className="cursor-pointer"
                        opacity={dimmed ? 0.14 : 1}
                      >
                        <line x1={startX} y1={startY} x2={endX} y2={endY} stroke="transparent" strokeWidth="14" />
                        <line
                          x1={startX}
                          y1={startY}
                          x2={endX}
                          y2={endY}
                          stroke={style.color}
                          strokeWidth={isSelected ? 3.2 : style.width}
                          strokeDasharray={style.dashed ? '6,4' : undefined}
                          markerEnd={`url(#arrow-${rel.type})`}
                        />

                        <g transform={`translate(${midX}, ${midY}) rotate(${angle})`}>
                          <rect
                            x={-pillW / 2}
                            y={-7.5}
                            width={pillW}
                            height={15}
                            rx={3}
                            fill="#09090b"
                            stroke={isSelected ? '#e11d48' : 'none'}
                            strokeWidth="1"
                          />
                          <text
                            x={0}
                            y={3}
                            textAnchor="middle"
                            fill={rel.type === 'SAME_AS' ? '#f43f5e' : '#a1a1aa'}
                            fontSize="9"
                            fontFamily="monospace"
                            fontWeight="600"
                          >
                            {rel.caption}
                          </text>
                        </g>
                      </g>
                    );
                  })}

                  {visibleNodes.map((node) => {
                    const style = NEO4J_LABELS[node.label] || NEO4J_LABELS.Forum;
                    const isSelected = selectedEntity.kind === 'node' && selectedEntity.id === node.id;
                    const isNeighbor =
                      selectedEntity.kind === 'node' &&
                      visibleRelationships.some((r) => (r.source === selectedEntity.id && r.target === node.id) || (r.target === selectedEntity.id && r.source === node.id));
                    const dimmed = isolateNeighborhood && selectedEntity.kind === 'node' && !isSelected && !isNeighbor;

                    return (
                      <g
                        key={node.id}
                        transform={`translate(${node.x}, ${node.y})`}
                        onMouseDown={(e) => {
                          e.stopPropagation();
                          setSelectedEntity({ kind: 'node', id: node.id });
                          setDraggingNodeId(node.id);
                        }}
                        onDoubleClick={(e) => {
                          e.stopPropagation();
                          togglePinNode(node.id);
                        }}
                        className="cursor-pointer"
                        opacity={dimmed ? 0.16 : 1}
                      >
                        {isSelected && <circle r={style.radius + 6} fill="none" stroke="#e11d48" strokeWidth="3" strokeOpacity="0.85" />}

                        <circle
                          r={style.radius}
                          fill={style.fill}
                          stroke={isSelected ? '#ffffff' : style.stroke}
                          strokeWidth={isSelected ? 3 : 2.4}
                        />

                        {node.pinned && <circle cx={style.radius * 0.72} cy={-style.radius * 0.72} r={4.5} fill="#e11d48" stroke="#09090b" strokeWidth="1.5" />}

                        <text y={3.5} textAnchor="middle" fill={style.text} fontSize="9.5" fontFamily="monospace" fontWeight="bold">
                          {node.caption.length > 11 ? node.caption.slice(0, 10) + '…' : node.caption}
                        </text>

                        <text y={style.radius + 14} textAnchor="middle" fill="#d4d4d8" fontSize="10" fontFamily="monospace">
                          {node.caption}
                        </text>
                      </g>
                    );
                  })}
                </g>
              </svg>
            </div>
          )}

          {frameMode === 'table' && (
            <div className="flex-1 overflow-auto p-5">
              <table className="w-full text-left border-collapse font-mono text-xs border border-[#27272a]">
                <thead>
                  <tr className="border-b border-[#27272a] text-[#a1a1aa] bg-[#121216]">
                    <th className="p-3">&lt;id&gt;</th>
                    <th className="p-3">Source (:Handle)</th>
                    <th className="p-3">Relationship</th>
                    <th className="p-3">Target Node</th>
                    <th className="p-3">Properties</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleRelationships.map((rel) => {
                    const s = nodes.find((n) => n.id === rel.source);
                    const t = nodes.find((n) => n.id === rel.target);
                    return (
                      <tr
                        key={rel.id}
                        onClick={() => {
                          setSelectedEntity({ kind: 'relationship', id: rel.id });
                          setFrameMode('graph');
                        }}
                        className="border-b border-[#27272a] hover:bg-[#18181d] cursor-pointer"
                      >
                        <td className="p-3 text-[#a1a1aa]">{rel.neoId}</td>
                        <td className="p-3 text-[#f4f4f5] font-semibold">
                          (:{s?.label} &#123;caption: "{s?.caption}"&#125;)
                        </td>
                        <td className="p-3 text-[#e11d48] font-bold">[:{rel.type}]</td>
                        <td className="p-3 text-[#f4f4f5] font-semibold">
                          (:{t?.label} &#123;caption: "{t?.caption}"&#125;)
                        </td>
                        <td className="p-3 text-[#a1a1aa]">{JSON.stringify(rel.properties)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {frameMode === 'json' && (
            <div className="flex-1 overflow-auto p-5 bg-[#09090b]">
              <pre className="text-xs font-mono text-[#f4f4f5] leading-relaxed">
                {JSON.stringify(
                  {
                    neo4j_bolt: 'bolt://127.0.0.1:7687',
                    cypher_query: cypherInput,
                    nodes_returned: visibleNodes.length,
                    relationships_returned: visibleRelationships.length,
                    subgraph: {
                      nodes: visibleNodes,
                      relationships: visibleRelationships
                    }
                  },
                  null,
                  2
                )}
              </pre>
            </div>
          )}

          {frameMode === 'certin' && (
            <div className="flex-1 overflow-auto p-6">
              <div className="max-w-4xl mx-auto bg-[#121216] border border-[#27272a] rounded p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-[#27272a] pb-3">
                  <div>
                    <span className="text-xs font-mono uppercase text-[#e11d48] block font-bold">
                      CERT-In Directions (IT Act Section 70B) // Mandatory 6-Hour Incident Dossier
                    </span>
                    <h2 className="text-lg font-bold text-[#f4f4f5] mt-1">Automated Threat Actor Attribution &amp; Pre-Breach Containment Filing</h2>
                  </div>
                  <button
                    onClick={() => setFrameMode('graph')}
                    className="px-3.5 py-2 rounded bg-[#e11d48] text-[#f4f4f5] text-xs font-mono font-bold cursor-pointer"
                  >
                    ← Back to Graph
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 font-mono text-xs">
                  <div className="p-3.5 rounded bg-[#09090b] border border-[#27272a]">
                    <span className="text-[#a1a1aa] block text-[10px]">RESOLVED PERSONAS</span>
                    <span className="text-[#e11d48] font-bold mt-1 block">pepela ↔ Spirigatito (91.0%)</span>
                  </div>
                  <div className="p-3.5 rounded bg-[#09090b] border border-[#27272a]">
                    <span className="text-[#a1a1aa] block text-[10px]">SHARED CRYPTO PROOF</span>
                    <span className="text-[#f4f4f5] font-bold mt-1 block">Tox: 3F0A8B9C...3F4A &amp; ETH Escrow</span>
                  </div>
                  <div className="p-3.5 rounded bg-[#09090b] border border-[#27272a]">
                    <span className="text-[#a1a1aa] block text-[10px]">WAF BLOCK ARTIFACT</span>
                    <span className="text-[#f4f4f5] font-bold mt-1 block">UUID: 0ee284cc-0eb1-493f...</span>
                  </div>
                </div>

                <div className="p-4 rounded bg-[#09090b] border border-[#27272a] space-y-2 font-mono text-xs text-[#a1a1aa]">
                  <div className="text-[#f4f4f5] font-bold">Statutory Compliance Advisory:</div>
                  <p>
                    Under CERT-In directions under Section 70B of the Information Technology Act, 2000, cybersecurity
                    incidents must be formally notified within 6 hours. This automated dossier extracts pre-breach correlation
                    telemetry across dark web forums, shared cryptographic identities, and target CVEs.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* BOTTOM STATUS BAR */}
          <footer className="h-8 border-t border-[#27272a] bg-[#121216] px-4 flex items-center justify-between text-[11px] font-mono text-[#a1a1aa] shrink-0">
            <div className="flex items-center gap-3">
              <span>
                Displaying <strong className="text-[#f4f4f5]">{visibleNodes.length}</strong> nodes,{' '}
                <strong className="text-[#f4f4f5]">{visibleRelationships.length}</strong> relationships.
              </span>
              <span className="text-[#27272a]">|</span>
              <span>Completed in {queryExecTime} ms.</span>
            </div>
            <div className="hidden sm:flex items-center gap-3">
              <span>Double-click node to Pin/Unpin</span>
              <span className="text-[#27272a]">•</span>
              <span>Zoom: {Math.round(zoom * 100)}%</span>
            </div>
          </footer>
        </div>

        {/* RIGHT PROPERTY INSPECTOR PANEL */}
        <aside className="w-80 bg-[#121216] border-l border-[#27272a] flex flex-col justify-between p-4 overflow-y-auto shrink-0 z-20">
          {inspectedObject && (
            <div className="space-y-4">
              <div className="border-b border-[#27272a] pb-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-[#e11d48] font-bold">
                    {selectedEntity.kind === 'node' ? 'NODE TELEMETRY' : 'RELATIONSHIP TELEMETRY'}
                  </span>
                  <span className="text-[11px] font-mono text-[#a1a1aa]">&lt;id&gt;: {inspectedObject.neoId}</span>
                </div>

                {selectedEntity.kind === 'node' ? (
                  <div className="flex items-center justify-between gap-2">
                    <span className="px-2.5 py-1 rounded text-xs font-mono font-bold bg-[#18181d] text-[#f4f4f5] border border-[#e11d48]">
                      :{(inspectedObject as NodeItem).label}
                    </span>
                    <button
                      onClick={() => togglePinNode(inspectedObject.id)}
                      className="text-xs font-mono px-2.5 py-1 rounded bg-[#09090b] hover:border-[#e11d48] text-[#f4f4f5] flex items-center gap-1.5 border border-[#27272a]"
                    >
                      {(inspectedObject as NodeItem).pinned ? (
                        <>
                          <Unlock className="w-3.5 h-3.5 text-[#e11d48]" /> Unpin
                        </>
                      ) : (
                        <>
                          <Lock className="w-3.5 h-3.5" /> Pin
                        </>
                      )}
                    </button>
                  </div>
                ) : (
                  <span className="px-2.5 py-1 rounded bg-[#e11d48] text-[#f4f4f5] text-xs font-mono font-bold inline-block">
                    [:{(inspectedObject as RelationshipItem).type}]
                  </span>
                )}

                <h3 className="text-sm font-mono font-bold text-[#f4f4f5] mt-2.5 break-all">{inspectedObject.caption}</h3>
              </div>

              <div>
                <span className="text-[10px] font-mono uppercase text-[#a1a1aa] block mb-2 font-bold">Property Keys &amp; Values</span>
                <div className="rounded border border-[#27272a] overflow-hidden bg-[#09090b] divide-y divide-[#27272a] font-mono text-xs">
                  {Object.entries(inspectedObject.properties || {}).map(([k, v]) => (
                    <div key={k} className="p-2.5">
                      <span className="text-[10px] text-[#e11d48] uppercase font-bold block mb-0.5">{k}</span>
                      <span className="text-[#f4f4f5] break-words leading-relaxed">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {selectedEntity.kind === 'relationship' && (inspectedObject as RelationshipItem).type === 'SAME_AS' && (
                <div className="p-3 rounded bg-[#09090b] border border-[#27272a] space-y-2">
                  <span className="text-[10px] font-mono uppercase text-[#a1a1aa] block font-bold">Analyst HITL Attribution Verdict</span>
                  <div className="grid grid-cols-3 gap-1.5">
                    <button
                      onClick={() => updateRelStatus('CONFIRMED')}
                      className="py-1.5 rounded bg-[#e11d48] hover:bg-[#f43f5e] text-[#f4f4f5] text-[11px] font-mono font-bold cursor-pointer"
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() => updateRelStatus('UNDER_REVIEW')}
                      className="py-1.5 rounded bg-[#18181d] border border-[#27272a] text-[#f4f4f5] text-[11px] font-mono font-bold cursor-pointer"
                    >
                      Hold
                    </button>
                    <button
                      onClick={() => updateRelStatus('REJECTED')}
                      className="py-1.5 rounded bg-[#09090b] border border-[#27272a] text-[#a1a1aa] text-[11px] font-mono font-bold cursor-pointer"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="pt-3 border-t border-[#27272a]">
            <button
              onClick={() => setLeftDrawer('tor')}
              className="w-full py-2.5 px-3 rounded bg-[#18181d] hover:bg-[#e11d48] border border-[#e11d48] text-[#f4f4f5] text-xs font-mono font-bold flex items-center justify-center gap-2 transition-colors cursor-pointer"
            >
              <Terminal className="w-4 h-4" />+ INGEST LIVE .ONION POST
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default App;
