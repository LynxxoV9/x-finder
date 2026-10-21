import { ConversationSummary, ConversationDetails } from '../types';

const API_BASE = '/api';

export async function fetchConversations(): Promise<ConversationSummary[]> {
  const res = await fetch(`${API_BASE}/conversations`);
  if (!res.ok) throw new Error('Impossible de charger les conversations');
  const data = await res.json();
  return data.conversations || [];
}

export async function fetchConversationDetails(id: number): Promise<ConversationDetails> {
  const res = await fetch(`${API_BASE}/conversations/${id}`);
  if (!res.ok) throw new Error(`Impossible de charger la conversation ${id}`);
  const data = await res.json();
  return data.conversation;
}

export async function createNewConversation(title?: string, model?: string): Promise<{ id: number; title: string; model: string }> {
  const res = await fetch(`${API_BASE}/conversations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, model }),
  });
  if (!res.ok) throw new Error('Erreur création conversation');
  const data = await res.json();
  return data.conversation;
}

export async function deleteConversation(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/conversations/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Erreur suppression conversation');
}

export async function sendChatMessage(
  conversationId: number | null,
  message: string,
  model?: string,
  imageBase64?: string
): Promise<any> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      conversation_id: conversationId,
      message,
      model,
      image_base64: imageBase64,
    }),
  });
  if (!res.ok) throw new Error('Erreur lors de la réponse de l’agent');
  return res.json();
}

export async function respondConfirmation(confirmationId: number, confirmed: boolean): Promise<any> {
  const res = await fetch(`${API_BASE}/confirmations/${confirmationId}/respond`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirmed }),
  });
  if (!res.ok) throw new Error('Erreur validation confirmation');
  return res.json();
}

export async function uploadImageFile(file: File): Promise<{ filename: string; path: string; data_url: string }> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Échec upload image');
  return res.json();
}

export async function fetchTools(): Promise<any> {
  const res = await fetch(`${API_BASE}/tools`);
  if (!res.ok) throw new Error('Impossible de charger les outils');
  return res.json();
}

export async function fetchHealth(): Promise<any> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Impossible de vérifier l’état');
  return res.json();
}
