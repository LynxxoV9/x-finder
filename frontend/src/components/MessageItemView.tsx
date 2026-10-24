import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Globe,
  CloudSun,
  Calendar,
  Mail,
  FileText,
  Folder,
  ShieldAlert,
  Target,
  Eye,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Terminal,
  Network,
  Search,
  Copy,
  Pencil,
  RotateCcw,
} from 'lucide-react';
import { MessageItem, ToolExecutionRecord } from '../types';
import { MermaidChart } from './MermaidChart';
import { Language } from '../i18n/translations';

interface MessageItemViewProps {
  message: MessageItem;
  tools?: ToolExecutionRecord[];
  lang: Language;
  isLoading: boolean;
  onRetry: (message: MessageItem) => void;
  onEdit: (message: MessageItem) => void;
}

export const MessageItemView: React.FC<MessageItemViewProps> = ({
  message,
  tools = [],
  lang,
  isLoading,
  onRetry,
  onEdit,
}) => {
  const [copyStatus, setCopyStatus] = useState('');

  if (message.role === 'user') {
    const isFrench = lang === 'fr';
    const copyMessage = async () => {
      try {
        await navigator.clipboard.writeText(message.content || '');
        setCopyStatus(isFrench ? 'Copié' : 'Copied');
      } catch {
        setCopyStatus(isFrench ? 'Copie impossible' : 'Copy failed');
      }
      window.setTimeout(() => setCopyStatus(''), 2000);
    };

    return (
      <div className="message-row user">
        <div className="user-message-content">
          <div className="user-bubble">
            {message.content}
            {message.image_url && (
              <img
                src={message.image_url}
                alt={isFrench ? "Média d'investigation" : 'Attached image'}
                className="user-image-preview"
              />
            )}
          </div>
          <div className="message-actions">
            <button
              type="button"
              onClick={() => void copyMessage()}
              title={isFrench ? 'Copier la question' : 'Copy prompt'}
              aria-label={isFrench ? 'Copier la question' : 'Copy prompt'}
            >
              <Copy size={14} />
              <span>{copyStatus || (isFrench ? 'Copier' : 'Copy')}</span>
            </button>
            <button
              type="button"
              onClick={() => onEdit(message)}
              disabled={isLoading}
              title={isFrench ? 'Modifier la question' : 'Edit prompt'}
              aria-label={isFrench ? 'Modifier la question' : 'Edit prompt'}
            >
              <Pencil size={14} />
              <span>{isFrench ? 'Modifier' : 'Edit'}</span>
            </button>
            <button
              type="button"
              onClick={() => onRetry(message)}
              disabled={isLoading}
              title={isFrench ? 'Relancer cette question' : 'Retry this prompt'}
              aria-label={isFrench ? 'Relancer cette question' : 'Retry this prompt'}
            >
              <RotateCcw size={14} />
              <span>{isFrench ? 'Relancer' : 'Retry'}</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Si c'est un message intermédiaire ou assistant
  if (message.role === 'assistant' && message.content) {
    return (
      <div className="message-row assistant">
        <div className="assistant-body">
          {/* Timeline des outils associés à cette étape */}
          {tools.length > 0 && (
            <div className="tool-timeline">
              {tools.map((t, idx) => (
                <ToolBadge key={idx} tool={t} />
              ))}
            </div>
          )}

          {/* Corps de la réponse markdown */}
          <div className="assistant-bubble">
            <ReactMarkdown
              components={{
                code({ node, inline, className, children, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || '');
                  if (!inline && match && match[1] === 'mermaid') {
                    return <MermaidChart chart={String(children).replace(/\n$/, '')} />;
                  }
                  return (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        </div>
      </div>
    );
  }

  return null;
};

// Composant Badge / Carte pour chaque exécution d'outil
const ToolBadge: React.FC<{ tool: ToolExecutionRecord }> = ({ tool }) => {
  const [open, setOpen] = useState(false);

  // Sélection d'icône selon l'outil
  const getIcon = (name: string) => {
    switch (name) {
      case 'search_web':
        return <Globe size={14} className="tool-icon" />;
      case 'get_weather':
        return <CloudSun size={14} className="tool-icon" />;
      case 'list_calendar_events':
      case 'search_calendar_events':
      case 'create_calendar_event':
      case 'delete_calendar_event':
        return <Calendar size={14} className="tool-icon" />;
      case 'prepare_email_draft':
      case 'send_email_confirmed':
        return <Mail size={14} className="tool-icon" />;
      case 'search_notion':
      case 'read_notion_page':
      case 'create_notion_page':
      case 'append_to_notion_page':
        return <FileText size={14} className="tool-icon" />;
      case 'search_drive_files':
      case 'read_drive_file_content':
        return <Folder size={14} className="tool-icon" />;
      case 'recon_social_profile':
      case 'cti_threat_lookup':
        return <ShieldAlert size={14} className="tool-icon" />;
      case 'hunt_opportunities':
        return <Target size={14} className="tool-icon" />;
      case 'analyze_image_intel':
        return <Eye size={14} className="tool-icon" />;
      case 'query_local_knowledge':
        return <BookOpen size={14} className="tool-icon" />;
      case 'investigate_email_osint':
        return <Search size={14} className="tool-icon" />;
      case 'harvest_domain_intel':
        return <Network size={14} className="tool-icon" />;
      case 'generate_osint_graph':
        return <Network size={14} className="tool-icon" style={{ color: '#00f2fe' }} />;
      default:
        return <Terminal size={14} className="tool-icon" />;
    }
  };

  return (
    <div className="tool-badge-card">
      <div className="tool-header-line" onClick={() => setOpen(!open)}>
        <div className="tool-info">
          {getIcon(tool.tool_name)}
          <span>{tool.tool_name}</span>
          <span className={`tool-status-tag ${tool.status}`}>
            {tool.status === 'success' ? 'SUCCÈS' : 'ERREUR'}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="tool-time-pill">{tool.execution_time_ms} ms</span>
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </div>
      </div>

      {open && (
        <div className="tool-drawer-content">
          <div>
            <div className="tool-section-title">Arguments d'entrée :</div>
            <pre className="tool-code-preview">{JSON.stringify(tool.arguments, null, 2)}</pre>
          </div>
          {tool.output && (
            <div>
              <div className="tool-section-title">Résultat retourné :</div>
              <pre className="tool-code-preview">{JSON.stringify(tool.output, null, 2)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
