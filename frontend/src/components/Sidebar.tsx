import React from 'react';
import { Shield, Plus, Trash2, Cpu, Wrench } from 'lucide-react';
import { ConversationSummary } from '../types';

interface SidebarProps {
  conversations: ConversationSummary[];
  activeId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
  onDelete: (id: number) => void;
  selectedModel: string;
  onModelChange: (model: string) => void;
  onOpenToolsModal: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  selectedModel,
  onModelChange,
  onOpenToolsModal,
}) => {
  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div className="sidebar-header">
        <div className="brand-badge">
          <Shield className="brand-icon" size={22} />
          <span>X-FINDER</span>
        </div>
        <span className="brand-tag">AGENT v1.0</span>
      </div>

      {/* New Mission Button */}
      <button className="new-mission-btn" onClick={onNew}>
        <Plus size={16} />
        <span>Nouvelle Mission</span>
      </button>

      {/* Conversation History */}
      <div className="conv-list">
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`conv-item ${c.id === activeId ? 'active' : ''}`}
            onClick={() => onSelect(c.id)}
          >
            <span className="conv-title" title={c.title}>
              {c.title}
            </span>
            <button
              className="conv-del-btn"
              title="Supprimer"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(c.id);
              }}
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>

      {/* Sidebar Footer: Model and Tools */}
      <div className="sidebar-footer">
        <div className="model-selector">
          <label className="model-label">Modèle LLM (RodiumAI)</label>
          <select
            className="model-select"
            value={selectedModel}
            onChange={(e) => onModelChange(e.target.value)}
          >
            <option value="google/gemini-2.5-flash-lite">Gemini 2.5 Flash Lite</option>
            <option value="google/gemini-3.8-flash">Gemini 3.8 Flash</option>
            <option value="anthropic/claude-sonnet-4-5-20250929">Claude 3.5 Sonnet</option>
          </select>
        </div>

        <div className="tools-status-badge" onClick={onOpenToolsModal}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Wrench size={14} style={{ color: '#00f2fe' }} />
            <span>18 Outils Connectés</span>
          </div>
          <span style={{ color: '#00e676', fontSize: '0.72rem', fontWeight: 600 }}>ACTIFS</span>
        </div>
      </div>
    </aside>
  );
};
