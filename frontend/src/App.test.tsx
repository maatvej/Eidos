/**
 * Unit tests for root App component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { App } from "./App";
import { useAppStore } from "./store/useAppStore";
import { useToastStore } from "./store/toastStore";
import { api } from "./services/api";

describe("App component", () => {
  beforeEach(() => {
    useAppStore.setState({
      currentView: "studio",
      jobId: null,
      status: "IDLE",
      user: null,
      progress: 0,
      stepMessage: "",
      transcript: null,
      errorMessage: null,
    });
    useToastStore.setState({ toasts: [] });

    vi.spyOn(api.auth, "getCurrentUser").mockResolvedValue({
      id: 1,
      username: "alex",
      full_name: "Алексей Смирнов",
      email: "alex@example.com",
    });

    vi.spyOn(api.account, "getProfile").mockResolvedValue({
      id: 1,
      username: "alex",
      full_name: "Алексей Смирнов",
      email: "alex@example.com",
    });

    vi.spyOn(api.account, "getTranscriptions").mockResolvedValue({
      items: [],
      page: 1,
      limit: 10,
      total: 0,
      total_pages: 1,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should fetch current user on mount and render studio layout", async () => {
    render(<App />);

    await waitFor(() => {
      expect(api.auth.getCurrentUser).toHaveBeenCalled();
    });

    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByText("Загрузить аудиозапись встречи")).toBeInTheDocument();
    expect(screen.getByText("Исполнительная Выжимка Встречи")).toBeInTheDocument();
  });

  it("should switch to account management view when currentView is account", async () => {
    window.history.pushState({}, "", "/account/history");
    render(<App />);

    await waitFor(() => {
      expect(screen.queryByRole("main")).not.toBeInTheDocument();
      expect(screen.getByText("История транскрипций")).toBeInTheDocument();
    });
  });

  it("should establish SSE connection when job is in LOADING state and handle progress/complete events", async () => {
    useAppStore.setState({
      jobId: "sse-job-1",
      status: "LOADING",
      progress: 10,
      stepMessage: "Старт...",
    });

    vi.spyOn(api.transcription, "getJob").mockResolvedValue({
      id: "sse-job-1",
      filename: "audio.mp3",
      file_path: "/uploads/audio.mp3",
      status: "COMPLETED",
      progress_percentage: 100,
      result: {
        utterances: [
          { id: "u1", speaker: "Спикер 1", start: 0, end: 5, text: "Результат готов" },
        ],
        analysis: {
          title: "Завершенный анализ",
          executive_summary: "Все решения согласованы.",
        },
      },
      created_at: "2026-08-15T00:00:00Z",
      updated_at: "2026-08-15T00:05:00Z",
    });

    render(<App />);

    // Get created MockEventSource instance from setup
    const eventSourceClass = window.EventSource as unknown as { instances: any[] };
    expect(eventSourceClass.instances.length).toBeGreaterThan(0);
    const sseInstance = eventSourceClass.instances[eventSourceClass.instances.length - 1];

    expect(sseInstance.url).toBe("/api/v1/events/sse/sse-job-1");

    // Emit progress event
    act(() => {
      sseInstance.emit(
        "progress",
        JSON.stringify({ progress: 75, step: "ИИ обработка LLM..." })
      );
    });

    expect(useAppStore.getState().progress).toBe(75);
    expect(useAppStore.getState().stepMessage).toBe("ИИ обработка LLM...");

    // Emit complete event
    await act(async () => {
      sseInstance.emit("complete", JSON.stringify({ status: "COMPLETED" }));
    });

    await waitFor(() => {
      expect(useAppStore.getState().status).toBe("SUCCESS");
      expect(useAppStore.getState().progress).toBe(100);
      expect(useAppStore.getState().transcript?.utterances).toHaveLength(1);
    });

    expect(
      useToastStore.getState().toasts.some((t) => t.message.includes("успешно сформированы"))
    ).toBe(true);
  });
});
