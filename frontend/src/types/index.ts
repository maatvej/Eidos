/**
 * TypeScript type definitions for Eidos Voice Intelligence Platform.
 * Matches FastAPI Pydantic v2 schemas and domain models.
 */

export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
  confidence?: number;
  speaker?: string;
}

export interface Utterance {
  id: string;
  speaker: string;
  start: number;
  end: number;
  text: string;
  words?: WordTimestamp[];
}

export type ActionItemPriority = "HIGH" | "MEDIUM" | "LOW" | "ВЫСОКИЙ" | "СРЕДНИЙ" | "НИЗКИЙ";

export interface ActionItem {
  task: string;
  owner?: string;
  due_date?: string;
  priority: ActionItemPriority;
}

export type SentimentType = "POSITIVE" | "NEUTRAL" | "NEGATIVE" | "ПОЗИТИВНЫЙ" | "НЕЙТРАЛЬНЫЙ" | "НЕГАТИВНЫЙ";

export interface ConversationAnalysis {
  title?: string;
  timestamp?: string;
  executive_summary?: string;
  key_decisions?: string[];
  action_items?: ActionItem[];
  overall_sentiment?: SentimentType;
}

export interface TranscriptionResult {
  utterances: Utterance[];
  analysis?: ConversationAnalysis;
  title?: string;
  detected_language?: string;
  duration_seconds?: number;
  executive_summary?: {
    summary?: string;
    key_decisions?: string[];
    action_items?: ActionItem[];
    sentiment?: SentimentType;
  } | string;
}

export type JobStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED" | "CANCELLED" | "QUEUED_LOCAL" | "QUEUED_REDIS";

export interface TranscriptionJobEntity {
  id: string;
  filename: string;
  file_path: string;
  status: JobStatus;
  progress_percentage: number;
  current_step?: string;
  result?: TranscriptionResult;
  error_message?: string;
  created_at: string;
  updated_at: string;
  created_by?: string;
  version_id?: number;
}

export interface UserProfile {
  id?: number | string;
  username: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  full_name?: string;
  is_superuser?: boolean;
  is_staff?: boolean;
}

export interface AccountTranscriptionItem {
  id: string;
  title: string;
  original_filename: string;
  duration_seconds: number;
  status: string;
  created_at: string;
  transcription_text?: string;
  language?: string;
  audio_url?: string;
}

export interface PaginatedTranscriptions {
  items: AccountTranscriptionItem[];
  page: number;
  limit: number;
  total: number;
  total_pages: number;
}

export type AppTheme = "dark" | "light";

export type AppView = "studio" | "account";

export type UIJobStatus = "IDLE" | "LOADING" | "SUCCESS" | "ERROR";

export interface ToastNotification {
  id: string;
  message: string;
  type: "success" | "error" | "info" | "warning";
  duration?: number;
}
