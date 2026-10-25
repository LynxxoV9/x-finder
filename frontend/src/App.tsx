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
import {
  AuthUser,
  getAuthSession,
  logoutAccount,
  setCsrfToken,
} from './api/client';
import { AuthScreen } from './components/AuthScreen';
import { ProfileMenu } from './components/ProfileMenu';
import { ConversationSummary, ConversationDetails, MessageItem } from './types';
import { Language, translations } from './i18n/translations';
import { Shield } from 'lucide-react';
import './App.css';

const VALID_MODELS = [
  'google/gemini-3.8-flash',
  'anthropic/claude-sonnet-4-5-20250929',
  'google/gemini-3.5-flash',
];

export const App: React.FC = () => {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [activeDetails, setActiveDetails] = useState<ConversationDetails | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('google/gemini-3.8-flash');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isToolsModalOpen, setIsToolsModalOpen] = useState<boolean>(false);
  const [draftRequest, setDraftRequest] = useState<{
    id: number;
    text: string;
    imageUrl?: string;
  } | null>(null);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

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

  const lastAssistantMessage = [...(activeDetails?.messages || [])]
    .reverse()
    .find((msg) => msg.role === 'assistant' && !!msg.content);

  const confidenceMeta = (() => {
    const content = lastAssistantMessage?.content || '';
    const lower = content.toLowerCase();

    if (lower.includes('non confirmé') || lower.includes('non confirme')) return { label: 'Non confirmé', color: '#f59e0b' };
    if (lower.includes('confiance : faible') || lower.includes('faible')) return { label: 'Faible', color: '#f97316' };
    if (lower.includes('confiance : moyenne') || lower.includes('moyenne')) return { label: 'Moyenne', color: '#facc15' };
    if (lower.includes('confiance : élevée') || lower.includes('elevee') || lower.includes('élevée')) return { label: 'Élevée', color: '#22c55e' };
    return { label: 'Non signalé', color: '#64748b' };
  })();

  const graphDetected = (lastAssistantMessage?.content || '').includes('```mermaid');

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [activeDetails?.messages, isLoading]);

  useEffect(() => {
    getAuthSession()
      .then((user) => {
        setAuthUser(user);
        setCsrfToken(user.csrf_token);
        return loadConversations();
      })
      .catch(() => setAuthUser(null))
      .finally(() => setAuthLoading(false));
  }, []);

  const handleAuthenticated = (user: AuthUser) => {
    setAuthUser(user);
    setCsrfToken(user.csrf_token);
    void loadConversations();
  };

  const handleLogout = async () => {
    try {
      await logoutAccount();
      setAuthUser(null);
      setConversations([]);
      setActiveId(null);
      setActiveDetails(null);
    } catch (error) {
      console.error(error);
    }
  };

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
      if (details.model && VALID_MODELS.includes(details.model)) {
        setSelectedModel(details.model);
      } else {
        setSelectedModel('google/gemini-3.8-flash');
      }
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
      const errorMessage = e instanceof Error ? e.message : String(e);
      setActiveDetails((current) => ({
        id: current?.id || activeId || 0,
        title: current?.title || 'X-Finder Mission Hub',
        model: current?.model || selectedModel,
        messages: [
          ...(current?.messages || []),
          { role: 'assistant', content: `${t.request_error}: ${errorMessage}` },
        ],
        executed_tools: current?.executed_tools || [],
        pending_confirmations: current?.pending_confirmations || [],
      }));
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

  if (authLoading) {
    return <main className="auth-screen"><p className="auth-description">X-Finder…</p></main>;
  }
  if (!authUser) {
    return <AuthScreen lang={lang} onAuthenticated={handleAuthenticated} />;
  }

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
              <ProfileMenu
                user={authUser}
                lang={lang}
                onUpdated={setAuthUser}
                onLogout={() => void handleLogout()}
              />
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
                  return (
                    <MessageItemView
                      key={msg.id || index}
                      message={msg}
                      tools={toolsForMsg}
                      lang={lang}
                      isLoading={isLoading}
                      onRetry={(userMessage) => {
                        if (userMessage.content || userMessage.image_url) {
                          void handleSendMessage(userMessage.content || '', userMessage.image_url);
                        }
                      }}
                      onEdit={(userMessage) => setDraftRequest({
                        id: userMessage.id || index,
                        text: userMessage.content || '',
                        imageUrl: userMessage.image_url,
                      })}
                    />
                  );
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

          {lastAssistantMessage && (
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              margin: '0 12px 12px',
              padding: '8px 12px',
              border: '1px solid rgba(148, 163, 184, 0.2)',
              borderRadius: '10px',
              background: 'rgba(15, 23, 42, 0.7)',
              color: '#e2e8f0',
              fontSize: '0.8rem',
            }}>
              <span>
                Niveau de confiance : <strong style={{ color: confidenceMeta.color }}>{confidenceMeta.label}</strong>
              </span>
              <span style={{ opacity: 0.8 }}>
                {graphDetected ? 'Graphe Mermaid détecté' : 'Aucun graphe détecté'}
              </span>
            </div>
          )}

          <ChatInput
            onSend={handleSendMessage}
            isLoading={isLoading}
            lang={lang}
            draftRequest={draftRequest}
            onDraftConsumed={() => setDraftRequest(null)}
            onCancelDraft={() => setDraftRequest(null)}
          />
        </main>

        <ToolsModal isOpen={isToolsModalOpen} onClose={() => setIsToolsModalOpen(false)} lang={lang} />
      </div>
    </>
  );
};
export default App;
