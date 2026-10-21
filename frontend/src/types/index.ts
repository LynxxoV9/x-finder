// Types pour l'agent X-Finder

export interface ConversationSummary {
  id: number;
  title: string;
  model: string;
  created_at?: string;
  updated_at?: string;
}

export interface ToolExecutionRecord {
  id?: number;
  tool_name: string;
  arguments: any;
  output?: any;
  status: 'success' | 'error';
  execution_time_ms: number;
}

export interface PendingConfirmationItem {
  id: number;
  action_type: string;
  description: string;
  payload: {
    to?: string;
    subject?: string;
    body?: string;
    event_id?: string;
    [key: string]: any;
  };
}

export interface MessageItem {
  id?: number;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content?: string;
  tool_calls?: any[];
  tool_call_id?: string;
  name?: string;
  image_url?: string;
  created_at?: string;
}

export interface ConversationDetails {
  id: number;
  title: string;
  model: string;
  messages: MessageItem[];
  executed_tools: ToolExecutionRecord[];
  pending_confirmations: PendingConfirmationItem[];
}
