/**
 * Unit tests for TranscriptPlayer component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { TranscriptPlayer } from "./TranscriptPlayer";
import { useAppStore } from "../store/useAppStore";
import { useToastStore } from "../store/toastStore";
import { api } from "../services/api";
import { TranscriptionResult } from "../types";

describe("TranscriptPlayer component", () => {
  const mockTranscript: TranscriptionResult = {
    detected_language: "ru",
    duration_seconds: 12.0,
    title: "Интервью по продукту",
    utterances: [
      {
        id: "utt-1",
        speaker: "Интервьюер",
        start: 0.0,
        end: 4.5,
        text: "Расскажите подробнее о проекте.",
        words: [
          { word: "Расскажите", start: 0.0, end: 1.0, speaker: "Интервьюер" },
          { word: "подробнее", start: 1.1, end: 2.5, speaker: "Интервьюер" },
          { word: "о", start: 2.6, end: 2.9, speaker: "Интервьюер" },
          { word: "проекте.", start: 3.0, end: 4.5, speaker: "Интервьюер" },
        ],
      },
      {
        id: "utt-2",
        speaker: "Респондент",
        start: 5.0,
        end: 11.5,
        text: "Проект посвящен автоматизации распознавания речи.",
        words: [
          { word: "Проект", start: 5.0, end: 6.0, speaker: "Респондент" },
          { word: "посвящен", start: 6.1, end: 7.5, speaker: "Респондент" },
          { word: "автоматизации", start: 7.6, end: 9.0, speaker: "Респондент" },
          { word: "распознавания", start: 9.1, end: 10.5, speaker: "Респондент" },
          { word: "речи.", start: 10.6, end: 11.5, speaker: "Респондент" },
        ],
      },
    ],
  };

  beforeEach(() => {
    useAppStore.setState({
      jobId: "test-job-123",
      status: "IDLE",
      transcript: null,
      progress: 0,
      errorMessage: null,
      currentTime: 0,
      initialAudioTime: 0,
      initialSearchQuery: "",
    });
    useToastStore.setState({ toasts: [] });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should display placeholder when idle with no transcript", () => {
    render(<TranscriptPlayer />);
    expect(screen.getByText("Стенограмма Пока Не Сформирована")).toBeInTheDocument();
  });

  it("should display progress bar when in LOADING state", () => {
    useAppStore.setState({
      status: "LOADING",
      progress: 65,
      stepMessage: "Диаризация спикеров...",
    });

    render(<TranscriptPlayer />);
    expect(
      screen.getByText("ИИ Выполняет Диаризацию и Распознавание Речи...")
    ).toBeInTheDocument();
    expect(screen.getByText("Диаризация спикеров...")).toBeInTheDocument();
    expect(screen.getByText("65%")).toBeInTheDocument();
  });

  it("should display error state on processing failure", () => {
    useAppStore.setState({
      status: "ERROR",
      errorMessage: "Не удалось декодировать аудиофайл.",
    });

    render(<TranscriptPlayer />);
    expect(screen.getByText("Ошибка Обработки Аудио")).toBeInTheDocument();
    expect(screen.getByText("Не удалось декодировать аудиофайл.")).toBeInTheDocument();
  });

  it("should render transcript utterances, speaker tags and word spans", () => {
    useAppStore.setState({
      status: "SUCCESS",
      transcript: mockTranscript,
    });

    render(<TranscriptPlayer />);

    expect(screen.getByText("Интервью по продукту")).toBeInTheDocument();
    expect(screen.getByText("Язык: RU")).toBeInTheDocument();
    expect(screen.getAllByText("Интервьюер").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Респондент").length).toBeGreaterThan(0);
    expect(screen.getByText("Расскажите")).toBeInTheDocument();
    expect(screen.getByText("автоматизации")).toBeInTheDocument();
  });

  it("should filter and highlight words matching search query", () => {
    useAppStore.setState({
      status: "SUCCESS",
      transcript: mockTranscript,
    });

    render(<TranscriptPlayer />);

    const searchInput = screen.getByPlaceholderText("Поиск по стенограмме...");
    fireEvent.change(searchInput, { target: { value: "проект" } });

    expect(screen.getByText("1 из 2")).toBeInTheDocument();

    const nextBtn = screen.getByTitle("Следующее совпадение (Enter)");
    fireEvent.click(nextBtn);
    expect(screen.getByText("2 из 2")).toBeInTheDocument();

    const prevBtn = screen.getByTitle("Предыдущее совпадение (Shift+Enter)");
    fireEvent.click(prevBtn);
    expect(screen.getByText("1 из 2")).toBeInTheDocument();
  });

  it("should open export URLs when clicking format download buttons", () => {
    const windowOpenSpy = vi.spyOn(window, "open").mockImplementation(() => null);

    useAppStore.setState({
      jobId: "job-export-test",
      status: "SUCCESS",
      transcript: mockTranscript,
    });

    render(<TranscriptPlayer />);

    const pdfBtn = screen.getByText("Скачать PDF");
    fireEvent.click(pdfBtn);

    expect(windowOpenSpy).toHaveBeenCalledWith(
      "/api/v1/transcription/jobs/job-export-test/export?export_format=pdf",
      "_blank"
    );

    expect(
      useToastStore.getState().toasts.some((t) => t.message.includes("PDF"))
    ).toBe(true);
  });

  it("should open speaker rename modal, apply quick suggestion and save renamed speaker", async () => {
    vi.spyOn(api.transcription, "renameSpeaker").mockResolvedValue({
      id: "test-job-123",
      filename: "test.mp3",
      file_path: "/path/test.mp3",
      status: "COMPLETED",
      progress_percentage: 100,
      created_at: "2026-08-15T00:00:00Z",
      updated_at: "2026-08-15T00:05:00Z",
    });

    useAppStore.setState({
      jobId: "test-job-123",
      status: "SUCCESS",
      transcript: mockTranscript,
    });

    render(<TranscriptPlayer />);

    // Click speaker rename button on the first speaker chip
    const speakerButtons = screen.getAllByTitle("Нажмите, чтобы переименовать Интервьюер");
    fireEvent.click(speakerButtons[0]);

    expect(screen.getByText("Переименовать спикера")).toBeInTheDocument();

    // Click quick suggestion "Ведущий"
    const suggestionBtn = screen.getByText("Ведущий");
    fireEvent.click(suggestionBtn);

    const saveBtn = screen.getByText("Сохранить");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.transcription.renameSpeaker).toHaveBeenCalledWith(
        "test-job-123",
        "Интервьюер",
        "Ведущий"
      );
    });

    // Check store state updated
    const updated = useAppStore.getState().transcript;
    expect(updated?.utterances[0].speaker).toBe("Ведущий");
    expect(
      useToastStore.getState().toasts.some((t) => t.message.includes("успешно переименован"))
    ).toBe(true);
  });

  it("should show warning toast and keep modal open when attempting to save unchanged speaker name", async () => {
    useAppStore.setState({
      jobId: "test-job-123",
      status: "SUCCESS",
      transcript: mockTranscript,
    });

    render(<TranscriptPlayer />);

    const speakerButtons = screen.getAllByTitle("Нажмите, чтобы переименовать Интервьюер");
    fireEvent.click(speakerButtons[0]);

    expect(screen.getByText("Переименовать спикера")).toBeInTheDocument();

    // Click Save without changing speaker name
    const saveBtn = screen.getByText("Сохранить");
    fireEvent.click(saveBtn);

    // Verify warning toast is shown and modal is STILL open
    expect(
      useToastStore.getState().toasts.some((t) =>
        t.message.includes("совпадает с текущим")
      )
    ).toBe(true);
    expect(screen.getByText("Переименовать спикера")).toBeInTheDocument();
  });

  it("should close modal when clicking cancel button or pressing Escape", async () => {
    useAppStore.setState({
      jobId: "test-job-123",
      status: "SUCCESS",
      transcript: mockTranscript,
    });

    render(<TranscriptPlayer />);

    const speakerButtons = screen.getAllByTitle("Нажмите, чтобы переименовать Интервьюер");
    fireEvent.click(speakerButtons[0]);
    expect(screen.getByText("Переименовать спикера")).toBeInTheDocument();

    // Press Escape on input
    const input = screen.getByPlaceholderText("Введите имя (например, Иван Иванов)");
    fireEvent.keyDown(input, { key: "Escape" });

    expect(screen.queryByText("Переименовать спикера")).not.toBeInTheDocument();
  });
});
