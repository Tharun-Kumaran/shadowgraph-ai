import React, { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import type { Core } from 'cytoscape';
import type { GraphElements } from '../types';

interface GraphViewerProps {
  data: GraphElements;
  onSelectNode: (nodeId: string) => void;
  selectedNodeId?: string | null;
}

export const GraphViewer: React.FC<GraphViewerProps> = ({ data, onSelectNode, selectedNodeId }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: [
        ...data.nodes.map(n => ({
          group: 'nodes' as const,
          data: n.data,
        })),
        ...data.edges.map(e => ({
          group: 'edges' as const,
          data: e.data,
        })),
      ],
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#1e293b',
            'border-color': '#00e5ff',
            'border-width': 2,
            'label': 'data(label)',
            'color': '#f8fafc',
            'font-size': '11px',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'width': 36,
            'height': 36,
          },
        },
        {
          selector: 'node[type = "handle"]',
          style: {
            'background-color': '#8b5cf6',
            'border-color': '#c084fc',
            'shape': 'ellipse',
            'width': 44,
            'height': 44,
          },
        },
        {
          selector: 'node[type = "cve"]',
          style: {
            'background-color': '#ef4444',
            'border-color': '#f87171',
            'shape': 'diamond',
            'width': 40,
            'height': 40,
          },
        },
        {
          selector: 'node[type = "tox_id"]',
          style: {
            'background-color': '#f59e0b',
            'border-color': '#fbbf24',
            'shape': 'hexagon',
            'width': 42,
            'height': 42,
          },
        },
        {
          selector: 'node[type = "wallet"]',
          style: {
            'background-color': '#10b981',
            'border-color': '#34d399',
            'shape': 'round-rectangle',
            'width': 38,
            'height': 38,
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#334155',
            'target-arrow-color': '#334155',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-size': '9px',
            'color': '#64748b',
            'text-rotation': 'autorotate',
          },
        },
        {
          selector: 'edge[label = "SAME_AS"]',
          style: {
            'line-color': '#f59e0b',
            'target-arrow-color': '#f59e0b',
            'line-style': 'dashed',
            'width': 3,
          },
        },
        {
          selector: ':selected',
          style: {
            'border-width': 4,
            'border-color': '#ffffff',
            'line-color': '#00e5ff',
            'target-arrow-color': '#00e5ff',
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: false,
        padding: 50,
      },
    });

    cy.on('tap', 'node', evt => {
      const node = evt.target;
      onSelectNode(node.id());
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
    };
  }, [data]);

  useEffect(() => {
    if (cyRef.current && selectedNodeId) {
      cyRef.current.$(`node[id = "${selectedNodeId}"]`).select();
    }
  }, [selectedNodeId]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: '100%',
          backgroundColor: '#090e17',
          borderRadius: '8px',
          border: '1px solid #1c2d4a',
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: 12,
          right: 12,
          background: 'rgba(13, 21, 36, 0.85)',
          padding: '6px 12px',
          borderRadius: '6px',
          border: '1px solid #1c2d4a',
          fontSize: '11px',
          color: '#94a3b8',
          display: 'flex',
          gap: '12px',
          pointerEvents: 'none',
        }}
      >
        <span><span style={{ color: '#8b5cf6' }}>●</span> Handle</span>
        <span><span style={{ color: '#f59e0b' }}>⬡</span> Tox ID</span>
        <span><span style={{ color: '#10b981' }}>■</span> Wallet</span>
        <span><span style={{ color: '#ef4444' }}>◆</span> CVE</span>
        <span><span style={{ color: '#f59e0b' }}>--</span> Candidate Clue</span>
      </div>
    </div>
  );
};
