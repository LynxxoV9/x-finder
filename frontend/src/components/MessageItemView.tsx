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
} from 'lucide-react';
import { MessageItem, ToolExecutionRecord } from '../types';

interface MessageItemViewProps {
  message: MessageItem;
  tools?: ToolExecutionRecord[];
}

export const MessageItemView: React.FC<MessageItemViewProps> = ({ message, tools = [] }) => {
  if (message.role === 'user') {
    return (
      <div className="message-row user">
        <div className="user-bubble">
          {message.content}
          {message.image_url && (
            <img
              src={message.image_url}
              alt="Média d'investigation"
              className="user-image-preview"
            />
          )}
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
            <ReactMarkdown>{message.content}</ReactMarkdown>
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
