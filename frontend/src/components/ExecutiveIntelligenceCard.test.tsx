/**
 * Unit tests for ExecutiveIntelligenceCard component.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ExecutiveIntelligenceCard } from "./ExecutiveIntelligenceCard";
import { useAppStore } from "../store/useAppStore";
import { useToastStore } from "../store/toastStore";
import { TranscriptionResult } from "../types";

describe("ExecutiveIntelligenceCard component", () => {
  beforeEach(() => {
    useAppStore.setState({
      status: "IDLE",
      transcript: null,
      errorMessage: null,
    });
    useToastStore.setState({ toasts: [] });
  });

  it("should render placeholder message when idle and no transcript available", () => {
    render(<ExecutiveIntelligenceCard />);
    expect(screen.getByText("Исполнительная Выжимка Встречи")).toBeInTheDocument();
    expect(
      screen.getByText(/Загрузите аудиозапись встречи, чтобы получить структурированное резюме/i)
    ).toBeInTheDocument();
  });

  it("should render loading skeleton when status is LOADING", () => {
    useAppStore.setState({ status: "LOADING" });
    const { container } = render(<ExecutiveIntelligenceCard />);

    expect(screen.getByText("ИИ-Аналитика Встречи")).toBeInTheDocument();
    const skeletons = container.getElementsByClassName("skeleton-line");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("should render error message when status is ERROR", () => {
    useAppStore.setState({
      status: "ERROR",
      errorMessage: "Сбой модели суммаризации текста",
    });

    render(<ExecutiveIntelligenceCard />);
    expect(screen.getByText("Не удалось сформировать аналитику")).toBeInTheDocument();
    expect(screen.getByText("Сбой модели суммаризации текста")).toBeInTheDocument();
  });

  it("should render full analytics card with sentiment, decisions, action items and summary", () => {
    const mockTranscript: TranscriptionResult = {
      utterances: [],
      analysis: {
        title: "Стратегическая сессия Q3",
        timestamp: "15.08.2026",
        overall_sentiment: "POSITIVE",
        executive_summary: "Обсудили запуск нового релиза и ключевые метрики.",
        key_decisions: ["Утвердить бюджет", "Перейти на микросервисы"],
        action_items: [
          {
            task: "Подготовить спецификацию",
            owner: "Дмитрий",
            due_date: "20.08.2026",
            priority: "HIGH",
          },
          {
            task: "Обновить документацию",
            owner: "Анна",
            due_date: "25.08.2026",
            priority: "LOW",
          },
        ],
      },
    };

    useAppStore.setState({
      status: "SUCCESS",
      transcript: mockTranscript,
    });

    render(<ExecutiveIntelligenceCard />);

    expect(screen.getByText("Стратегическая сессия Q3")).toBeInTheDocument();
    expect(screen.getByText("15.08.2026")).toBeInTheDocument();
    expect(screen.getByText("Тональность: Позитивный")).toBeInTheDocument();
    expect(
      screen.getByText("Обсудили запуск нового релиза и ключевые метрики.")
    ).toBeInTheDocument();
    expect(screen.getByText("Утвердить бюджет")).toBeInTheDocument();
    expect(screen.getByText("Перейти на микросервисы")).toBeInTheDocument();
    expect(screen.getByText("Подготовить спецификацию")).toBeInTheDocument();
    expect(screen.getByText("Дмитрий")).toBeInTheDocument();
    expect(screen.getByText("ВЫСОКИЙ")).toBeInTheDocument();
    expect(screen.getByText("НИЗКИЙ")).toBeInTheDocument();
  });

  it("should copy executive summary to clipboard when clicking copy button", async () => {
    const mockTranscript: TranscriptionResult = {
      utterances: [],
      analysis: {
        title: "Встреча",
        executive_summary: "Краткий текст.",
        key_decisions: ["Решение 1"],
        action_items: [
          {
            task: "Задача 1",
            owner: "Иван",
            priority: "MEDIUM",
          },
        ],
      },
    };

    useAppStore.setState({
      status: "SUCCESS",
      transcript: mockTranscript,
    });

    render(<ExecutiveIntelligenceCard />);

    const copyBtn = screen.getByRole("button", { name: /Скопировать/i });
    fireEvent.click(copyBtn);

    expect(navigator.clipboard.writeText).toHaveBeenCalled();
    const calls = vi.mocked(navigator.clipboard.writeText).mock.calls;
    expect(calls[0][0]).toContain("=== EIDOS ИИ-АНАЛИТИКА ВСТРЕЧИ ===");
    expect(calls[0][0]).toContain("Краткий текст.");
    expect(calls[0][0]).toContain("Решение 1");
    expect(calls[0][0]).toContain("Задача 1");

    await waitFor(() => {
      expect(
        useToastStore
          .getState()
          .toasts.some((t) => t.message.includes("Выжимка скопирована"))
      ).toBe(true);
    });
  });
});
