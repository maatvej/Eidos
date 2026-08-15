/**
 * Centralized Typed API Client for FastAPI & Django Backend Services.
 */

import {
  AccountTranscriptionItem,
  PaginatedTranscriptions,
  TranscriptionJobEntity,
  UserProfile,
} from "../types";

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };

  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    const returnUrl = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = `/accounts/login/?next=${returnUrl}`;
    throw new ApiError(401, "Unauthorized");
  }

  if (!response.ok) {
    let errorData = null;
    try {
      errorData = await response.json();
    } catch {
      // Ignored
    }
    const message =
      (errorData && (errorData.detail || errorData.message)) ||
      `HTTP Error ${response.status}: ${response.statusText}`;
    throw new ApiError(response.status, message, errorData);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
  auth: {
    getCurrentUser: (signal?: AbortSignal) =>
      request<UserProfile>("/api/v1/auth/me", { signal }),
  },

  transcription: {
    getJob: (jobId: string, signal?: AbortSignal) =>
      request<TranscriptionJobEntity>(`/api/v1/transcription/jobs/${jobId}`, { signal }),
    renameSpeaker: (jobId: string, oldName: string, newName: string, signal?: AbortSignal) =>
      request<TranscriptionJobEntity>(`/api/v1/transcription/jobs/${jobId}/speaker-rename`, {
        method: "POST",
        body: JSON.stringify({
          old_speaker_label: oldName,
          new_speaker_name: newName,
        }),
        signal,
      }),
    getAudioUrl: (jobId: string) => `/api/v1/transcription/jobs/${jobId}/audio`,
    getExportUrl: (jobId: string, format: string) =>
      `/api/v1/transcription/jobs/${jobId}/export?export_format=${format}`,
  },

  account: {
    getProfile: (signal?: AbortSignal) =>
      request<UserProfile>("/api/v1/account/me", { signal }),
    updateProfile: (
      data: { first_name?: string; last_name?: string; email?: string },
      signal?: AbortSignal
    ) =>
      request<UserProfile>("/api/v1/account/me", {
        method: "PATCH",
        body: JSON.stringify(data),
        signal,
      }),
    changePassword: (
      data: { current_password?: string; new_password?: string },
      signal?: AbortSignal
    ) =>
      request<{ status: string }>("/api/v1/account/me", {
        method: "PATCH",
        body: JSON.stringify(data),
        signal,
      }),
    getTranscriptions: (
      params: { page?: number; limit?: number; search?: string; sort_by?: string },
      signal?: AbortSignal
    ) => {
      const qs = new URLSearchParams();
      if (params.page) qs.append("page", params.page.toString());
      if (params.limit) qs.append("limit", params.limit.toString());
      if (params.search) qs.append("search", params.search);
      if (params.sort_by) qs.append("sort_by", params.sort_by);
      return request<PaginatedTranscriptions>(`/api/v1/account/transcriptions?${qs.toString()}`, {
        signal,
      });
    },
    getTranscriptionDetail: (id: string, signal?: AbortSignal) =>
      request<AccountTranscriptionItem>(`/api/v1/account/transcriptions/${id}`, { signal }),
    deleteTranscription: (id: string, signal?: AbortSignal) =>
      request<void>(`/api/v1/account/transcriptions/${id}`, {
        method: "DELETE",
        signal,
      }),
  },
};
