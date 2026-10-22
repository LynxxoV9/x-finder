import React, { useEffect, useState, useRef } from 'react';
import {
  Sidebar,
  MessageItemView,
  ConfirmationCard,
  ChatInput,
  ToolsModal,
  AmbientLightBackground,
} from './components';
import {
  fetchConversations,
  fetchConversationDetails,
  createNewConversation,
  deleteConversation,
  sendChatMessage,
  respondConfirmation,
} from './api/client';
import { ConversationSummary, ConversationDetails, MessageItem } from './types';
import { Language, translations } from './i18n/translations';
import { Shield } from 'lucide-react';
import './App.css';

export const App: React.FC = () => {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [activeDetails, setActiveDetails] = useState<ConversationDetails | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('google/gemini-2.5-flash-lite');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isToolsModalOpen, setIsToolsModalOpen] = useState<boolean>(false);

  // État bilingue Français / Anglais
  const [lang, setLang] = useState<Language>(() => {
    return (localStorage.getItem('xfinder_lang') as Language) || 'fr';
  });

  const toggleLang = () => {
    const nextLang = lang === 'fr' ? 'en' : 'fr';
    setLang(nextLang);
    localStorage.setItem('xfinder_lang', nextLang);
  };

  const t = translations[lang];
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [activeDetails?.messages, isLoading]);

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
      const title = lang === 'fr' ? 'Nouvelle Mission' : 'New Mission';
      const newConv = await createNewConversation(title, selectedModel);
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

  const quickPrompts = [
    {
      title: t.quick_multitool_title,
      desc: t.quick_multitool_desc,
      prompt: t.quick_multitool_prompt,
    },
    {
      title: t.quick_email_osint_title,
      desc: t.quick_email_osint_desc,
      prompt: t.quick_email_osint_prompt,
    },
    {
      title: t.quick_cti_title,
      desc: t.quick_cti_desc,
      prompt: t.quick_cti_prompt,
    },
    {
      title: t.quick_hunter_title,
      desc: t.quick_hunter_desc,
      prompt: t.quick_hunter_prompt,
    },
  ];

  return (
    <>
      {/* 1. Lumière ambiante en arrière-plan avec mouvement et variation d'intensité 3D */}
      <AmbientLightBackground />

      {/* 2. Interface utilisateur principale */}
      <div className="app-container">
        {/* Barre latérale */}
        <Sidebar
          conversations={conversations}
          activeId={activeId}
          onSelect={selectConversation}
          onNew={handleNewConversation}
          onDelete={handleDeleteConversation}
          selectedModel={selectedModel}
          onModelChange={setSelectedModel}
          onOpenToolsModal={() => setIsToolsModalOpen(true)}
          lang={lang}
          onToggleLang={toggleLang}
        />

        {/* Espace de discussion principal */}
        <main className="main-chat">
          <header className="chat-header">
            <div className="header-info">
              <h2>
                <span className="header-status-dot" />
                <span>{activeDetails?.title || 'X-Finder Mission Hub'}</span>
              </h2>
            </div>
            <div className="header-meta">
              <span>{t.online_region}</span>
            </div>
          </header>

          <div className="messages-container">
            {(!activeDetails || activeDetails.messages.length === 0) ? (
              <div className="empty-hud">
                <Shield className="empty-logo" />
                <h1>{t.empty_title}</h1>
                <p>{t.empty_desc}</p>

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
                  const toolsForMsg =
                    msg.role === 'assistant'
                      ? activeDetails.executed_tools.slice(index > 0 ? index - 1 : 0, index + 2)
                      : [];
                  return <MessageItemView key={msg.id || index} message={msg} tools={toolsForMsg} />;
                })}

                {activeDetails.pending_confirmations?.map((conf) => (
                  <ConfirmationCard
                    key={conf.id}
                    confirmation={conf}
                    onRespond={handleRespondConfirmation}
                    isLoading={isLoading}
                    lang={lang}
                  />
                ))}
              </>
            )}

            {isLoading && (
              <div className="message-row assistant">
                <div className="assistant-bubble" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ color: '#00f2fe', fontFamily: 'monospace', fontSize: '0.82rem' }}>
                    {t.agent_thinking}
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

          <ChatInput onSend={handleSendMessage} isLoading={isLoading} lang={lang} />
        </main>

        <ToolsModal isOpen={isToolsModalOpen} onClose={() => setIsToolsModalOpen(false)} lang={lang} />
      </div>
    </>
  );
};
export default App;
