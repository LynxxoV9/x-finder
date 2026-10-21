import React, { useEffect, useState, useRef } from 'react';
import {
  Sidebar,
  MessageItemView,
  ConfirmationCard,
  ChatInput,
  ToolsModal,
} from './components';
import {
  fetchConversations,
  fetchConversationDetails,
  createNewConversation,
  deleteConversation,
  sendChatMessage,
  respondConfirmation,
} from './api/client';
import { ConversationSummary, ConversationDetails, MessageItem, PendingConfirmationItem } from './types';
import { Shield, Sparkles, Terminal, Globe, CloudSun, Calendar, Mail, FileText, Folder } from 'lucide-react';
import './App.css';

export const App: React.FC = () => {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [activeDetails, setActiveDetails] = useState<ConversationDetails | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('google/gemini-2.5-flash-lite');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isToolsModalOpen, setIsToolsModalOpen] = useState<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Défilement automatique vers le bas
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [activeDetails?.messages, isLoading]);

  // Chargement initial des conversations
  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = async () => {
    try {
      const list = await fetchConversations();
      setConversations(list);
      if (list.length > 0 && !activeId) {
        selectConversation(list[0].id);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const selectConversation = async (id: number) => {
    try {
      setActiveId(id);
      const details = await fetchConversationDetails(id);
      setActiveDetails(details);
      if (details.model) setSelectedModel(details.model);
    } catch (e) {
      console.error(e);
    }
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await createNewConversation("Nouvelle Mission", selectedModel);
      await loadConversations();
      selectConversation(newConv.id);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteConversation = async (id: number) => {
    try {
      await deleteConversation(id);
      const remaining = conversations.filter((c) => c.id !== id);
      setConversations(remaining);
      if (activeId === id) {
        if (remaining.length > 0) {
          selectConversation(remaining[0].id);
        } else {
          setActiveId(null);
          setActiveDetails(null);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSendMessage = async (text: string, imageBase64?: string) => {
    setIsLoading(true);

    // Optimistic UI update for user message
    const tempUserMsg: MessageItem = {
      role: 'user',
      content: text,
      image_url: imageBase64,
    };

    if (activeDetails) {
      setActiveDetails({
        ...activeDetails,
        messages: [...activeDetails.messages, tempUserMsg],
      });
    }

    try {
      const result = await sendChatMessage(activeId, text, selectedModel, imageBase64);
      if (result.conversation_id) {
        await selectConversation(result.conversation_id);
        await loadConversations();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRespondConfirmation = async (confirmationId: number, confirmed: boolean) => {
    try {
      setIsLoading(true);
      await respondConfirmation(confirmationId, confirmed);
      if (activeId) {
        await selectConversation(activeId);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  // Missions rapides d'introduction
  const quickPrompts = [
    {
      title: '⚡ Défi Multi-Outils (Complet)',
      desc: 'Calendrier, Notion, Actualités IA & préparation de brouillon d’email.',
      prompt: 'Consulte mon Google Calendar pour demain, retrouve dans Notion mes notes sur le Machine Learning, recherche les actualités sur les agents IA et prépare un email pour professeur@universite.fr résumant ces éléments.',
    },
    {
      title: '🛡️ Veille CTI & Menaces',
      desc: 'Analyse d’une vulnérabilité critique et bulletin d’alerte.',
      prompt: 'Effectue une analyse CTI de la vulnérabilité CVE-2024-3094 : vecteurs d’attaque, score de gravité et mesures de mitigation.',
    },
    {
      title: '🎯 Chasse aux Opportunités',
      desc: 'Détection de stages, hackathons et CTFs en Cybersécurité.',
      prompt: 'Chasse les opportunités de stages et les compétitions CTF à venir en cybersécurité pour les profils étudiants passionnés.',
    },
    {
      title: '🌤️ Météo Comparée',
      desc: 'Comparaison météo multi-villes et prévisions.',
      prompt: 'Compare la météo actuelle et les prévisions entre Lomé et Accra.',
    },
  ];

  return (
    <div className="app-container">
      {/* Sidebar navigation */}
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={selectConversation}
        onNew={handleNewConversation}
        onDelete={handleDeleteConversation}
        selectedModel={selectedModel}
        onModelChange={setSelectedModel}
        onOpenToolsModal={() => setIsToolsModalOpen(true)}
      />

      {/* Main Chat HUD */}
      <main className="main-chat">
        {/* Header */}
        <header className="chat-header">
          <div className="header-info">
            <h2>
              <span className="header-status-dot" />
              <span>{activeDetails?.title || 'X-Finder Mission Hub'}</span>
            </h2>
          </div>
          <div className="header-meta">
            <span>Région : Automatique | Multi-outils Activé</span>
          </div>
        </header>

        {/* Message timeline */}
        <div className="messages-container">
          {(!activeDetails || activeDetails.messages.length === 0) ? (
            <div className="empty-hud">
              <Shield className="empty-logo" />
              <h1>X-Finder Intelligence Agent</h1>
              <p>
                Agent IA autonome avec <strong>Tool Calling</strong> dynamique. Spécialiste de la
                reconnaissance OSINT, de la Threat Intelligence (CTI) et de l'interconnexion d'outils
                (Tavily Web, Météo, Google Calendar, Notion, Google Drive, SMTP & RAG local).
              </p>

              <div className="quick-prompts-grid">
                {quickPrompts.map((qp, idx) => (
                  <div
                    key={idx}
                    className="quick-prompt-card"
                    onClick={() => handleSendMessage(qp.prompt)}
                  >
                    <div className="quick-prompt-title">{qp.title}</div>
                    <div className="quick-prompt-desc">{qp.desc}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <>
              {activeDetails.messages.map((msg, index) => {
                // Associer les outils exécutés
                const toolsForMsg =
                  msg.role === 'assistant'
                    ? activeDetails.executed_tools.slice(index > 0 ? index - 1 : 0, index + 2)
                    : [];
                return <MessageItemView key={msg.id || index} message={msg} tools={toolsForMsg} />;
              })}

              {/* Confirmations en attente (Sécurité humaine dans la boucle) */}
              {activeDetails.pending_confirmations?.map((conf) => (
                <ConfirmationCard
                  key={conf.id}
                  confirmation={conf}
                  onRespond={handleRespondConfirmation}
                  isLoading={isLoading}
                />
              ))}
            </>
          )}

          {isLoading && (
            <div className="message-row assistant">
              <div className="assistant-bubble" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: '#00f2fe', fontFamily: 'monospace', fontSize: '0.82rem' }}>
                  X-Finder analyse la requête et sélectionne les outils...
                </span>
                <span className="typing-indicator">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Chat input form */}
        <ChatInput onSend={handleSendMessage} isLoading={isLoading} />
      </main>

      {/* Tools Modal */}
      <ToolsModal isOpen={isToolsModalOpen} onClose={() => setIsToolsModalOpen(false)} />
    </div>
  );
};
export default App;
