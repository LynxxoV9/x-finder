import React, { useEffect, useState } from 'react';
import { X, Wrench, CheckCircle } from 'lucide-react';
import { fetchTools } from '../api/client';
import { Language, translations } from '../i18n/translations';

interface ToolsModalProps {
  isOpen: boolean;
  onClose: () => void;
  lang?: Language;
}

export const ToolsModal: React.FC<ToolsModalProps> = ({ isOpen, onClose, lang = 'fr' }) => {
  const [tools, setTools] = useState<any[]>([]);
  const t = translations[lang];

  useEffect(() => {
    if (isOpen) {
      fetchTools()
        .then((data) => setTools(data.tools || []))
        .catch(() => {});
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Wrench size={18} style={{ color: '#00f2fe' }} />
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>{t.tools_modal_title}</h3>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
          >
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <p style={{ fontSize: '0.82rem', color: '#94a3b8', lineHeight: 1.5 }}>
            {t.tools_modal_desc}
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {tools.map((item, idx) => (
              <div
                key={idx}
                style={{
                  background: '#090f1d',
                  border: '1px solid #1a2a47',
                  borderRadius: '6px',
                  padding: '10px 14px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontFamily: 'monospace', color: '#00f2fe', fontWeight: 600, fontSize: '0.85rem' }}>
                    {item.name}
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#00e676', fontSize: '0.72rem' }}>
                    <CheckCircle size={12} /> {t.tool_connected_badge}
                  </span>
                </div>
                <div style={{ fontSize: '0.78rem', color: '#cbd5e1' }}>{item.description}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
