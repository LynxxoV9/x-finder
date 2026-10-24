import { ConversationSummary, ConversationDetails } from '../types';

const API_BASE = '/api';
let csrfToken = '';

export interface AuthUser {
  id: number;
  email: string;
  display_name: string | null;
  csrf_token: string;
}

export function setCsrfToken(token: string) {
  csrfToken = token;
}

async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers);
  if (csrfToken && options.method && options.method !== 'GET') {
    headers.set('X-CSRF-Token', csrfToken);
  }
  return fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: 'same-origin',
  });
}

export async function getAuthSession(): Promise<AuthUser> {
  const res = await apiFetch('/auth/me');
  if (!res.ok) throw new Error('Session non authentifiée');
  return res.json();
}

export async function getAuthProviders(): Promise<{ google: boolean; github: boolean }> {
  const res = await apiFetch('/auth/providers');
  if (!res.ok) throw new Error('Impossible de charger les fournisseurs de connexion.');
  return res.json();
}

export async function registerAccount(
  email: string,
  password: string,
  displayName: string,
): Promise<AuthUser> {
  const res = await apiFetch('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Échec de la création du compte.');
  return data;
}

export async function loginAccount(email: string, password: string): Promise<AuthUser> {
  const res = await apiFetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Échec de la connexion.');
  return data;
}

export async function logoutAccount(): Promise<void> {
  const res = await apiFetch('/auth/logout', { method: 'POST' });
  if (!res.ok) throw new Error('Échec de la déconnexion.');
  setCsrfToken('');
}

export async function updateProfile(displayName: string): Promise<AuthUser> {
  const res = await apiFetch('/auth/me', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ display_name: displayName }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Impossible de mettre à jour le profil.');
  return data;
}

export async function fetchConversations(): Promise<ConversationSummary[]> {
  const res = await apiFetch('/conversations');
  if (!res.ok) throw new Error('Impossible de charger les conversations');
  const data = await res.json();
  return data.conversations || [];
}

export async function fetchConversationDetails(id: number): Promise<ConversationDetails> {
  const res = await apiFetch(`/conversations/${id}`);
  if (!res.ok) throw new Error(`Impossible de charger la conversation ${id}`);
  const data = await res.json();
  return data.conversation;
}

export async function createNewConversation(title?: string, model?: string): Promise<{ id: number; title: string; model: string }> {
  const res = await apiFetch('/conversations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, model }),
  });
  if (!res.ok) throw new Error('Erreur création conversation');
  const data = await res.json();
  return data.conversation;
}

export async function deleteConversation(id: number): Promise<void> {
  const res = await apiFetch(`/conversations/${id}`, {
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
  const res = await apiFetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      conversation_id: conversationId,
      message,
      model,
      image_base64: imageBase64,
    }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => null);
    throw new Error(error?.detail || `Erreur lors de la réponse de l’agent (${res.status})`);
  }
  return res.json();
}

export async function respondConfirmation(confirmationId: number, confirmed: boolean): Promise<any> {
  const res = await apiFetch(`/confirmations/${confirmationId}/respond`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirmed }),
  });
  if (!res.ok) throw new Error('Erreur validation confirmation');
  return res.json();
}

export async function uploadImageFile(file: File): Promise<{ filename: string; path: string | null; data_url: string }> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await apiFetch('/upload', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Échec upload image');
  return res.json();
}

export async function fetchTools(): Promise<any> {
  const res = await apiFetch('/tools');
  if (!res.ok) throw new Error('Impossible de charger les outils');
  return res.json();
}

export async function fetchHealth(): Promise<any> {
  const res = await apiFetch('/health');
  if (!res.ok) throw new Error('Impossible de vérifier l’état');
  return res.json();
}
