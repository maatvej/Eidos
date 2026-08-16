/**
 * Unit tests for AccountManagement component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AccountManagement } from "./AccountManagement";
import { useAppStore } from "../store/useAppStore";
import { useToastStore } from "../store/toastStore";
import { api } from "../services/api";

describe("AccountManagement component", () => {
  const mockTranscriptions = [
    {
      id: "tx-1",
      title: "Планерка команды разработки",
      original_filename: "sync.mp3",
      duration_seconds: 125,
      status: "COMPLETED",
      created_at: "2026-08-15T12:00:00Z",
      transcription_text: "Текст планерки разработки...",
    },
    {
      id: "tx-2",
      title: "Анализ требований",
      original_filename: "reqs.wav",
      duration_seconds: 300,
      status: "PROCESSING",
      created_at: "2026-08-15T14:00:00Z",
    },
  ];

  beforeEach(() => {
    useAppStore.setState({
      accountTab: "history",
      user: { username: "alex", first_name: "Алексей", email: "alex@example.com" },
    });
    useToastStore.setState({ toasts: [] });

    vi.spyOn(api.account, "getProfile").mockResolvedValue({
      username: "alex",
      first_name: "Алексей",
      last_name: "Иванов",
      email: "alex@example.com",
    });

    vi.spyOn(api.account, "getTranscriptions").mockResolvedValue({
      items: mockTranscriptions,
      page: 1,
      limit: 10,
      total: 2,
      total_pages: 1,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should render history tab and display list of user transcriptions", async () => {
    render(<AccountManagement />);

    expect(screen.getByText("История транскрипций")).toBeInTheDocument();
    expect(screen.getByText("Профиль")).toBeInTheDocument();
    expect(screen.getByText("Безопасность и пароль")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Планерка команды разработки")).toBeInTheDocument();
      expect(screen.getByText("Анализ требований")).toBeInTheDocument();
      expect(screen.getByText("02:05")).toBeInTheDocument(); // 125s
      expect(screen.getByText("05:00")).toBeInTheDocument(); // 300s
      expect(screen.getByText("Готово")).toBeInTheDocument();
      expect(screen.getByText("Обработка")).toBeInTheDocument();
    });
  });

  it("should navigate to studio view when clicking 'Студия' in history table", async () => {
    const navigateSpy = vi.fn();
    useAppStore.setState({ navigate: navigateSpy });

    render(<AccountManagement />);

    await waitFor(() => {
      expect(screen.getByText("Планерка команды разработки")).toBeInTheDocument();
    });

    const studioBtns = screen.getAllByTitle("Открыть в интерактивной студии");
    fireEvent.click(studioBtns[0]);

    expect(navigateSpy).toHaveBeenCalledWith("/jobs/tx-1");
  });

  it("should toggle dropdown details row and copy transcript text", async () => {
    render(<AccountManagement />);

    await waitFor(() => {
      expect(screen.getByText("Планерка команды разработки")).toBeInTheDocument();
    });

    const detailBtns = screen.getAllByTitle("Детали стенограммы");
    fireEvent.click(detailBtns[0]);

    expect(screen.getByText("Текст планерки разработки...")).toBeInTheDocument();

    const copyBtn = screen.getByText("Копировать текст");
    fireEvent.click(copyBtn);

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      "Текст планерки разработки..."
    );
    expect(
      useToastStore.getState().toasts.some((t) => t.message.includes("скопирован"))
    ).toBe(true);

    // Collapse details row via 'Свернуть' button
    const collapseBtn = screen.getByText("Свернуть");
    fireEvent.click(collapseBtn);
    expect(screen.queryByText("Текст планерки разработки...")).not.toBeInTheDocument();

    // Re-open and toggle closed via 'Детали' button again
    fireEvent.click(detailBtns[0]);
    expect(screen.getByText("Текст планерки разработки...")).toBeInTheDocument();

    const hideDetailsBtn = screen.getByTitle("Скрыть детали");
    fireEvent.click(hideDetailsBtn);
    expect(screen.queryByText("Текст планерки разработки...")).not.toBeInTheDocument();
  });

  it("should open delete confirmation modal and delete transcription item", async () => {
    vi.spyOn(api.account, "deleteTranscription").mockResolvedValue(undefined);

    render(<AccountManagement />);

    await waitFor(() => {
      expect(screen.getByText("Планерка команды разработки")).toBeInTheDocument();
    });

    const deleteBtns = screen.getAllByTitle("Удалить запись");
    fireEvent.click(deleteBtns[0]);

    expect(screen.getByText("Подтверждение удаления")).toBeInTheDocument();
    expect(
      screen.getByText(/Вы уверены, что хотите безвозвратно удалить запись/i)
    ).toBeInTheDocument();

    const confirmDeleteBtn = screen.getByText("Удалить безвозвратно");
    fireEvent.click(confirmDeleteBtn);

    await waitFor(() => {
      expect(api.account.deleteTranscription).toHaveBeenCalledWith("tx-1");
    });
  });

  it("should switch to Profile tab and submit profile update", async () => {
    const updateProfileSpy = vi.spyOn(api.account, "updateProfile").mockResolvedValue({
      username: "alex",
      first_name: "Александр",
      last_name: "Петров",
      email: "new_alex@example.com",
    });

    useAppStore.setState({ accountTab: "profile" });
    render(<AccountManagement />);

    await waitFor(() => {
      expect(screen.getByText("Личные данные профиля")).toBeInTheDocument();
    });

    const firstNameInput = screen.getByPlaceholderText("Иван");
    fireEvent.change(firstNameInput, { target: { value: "Александр" } });

    const submitBtn = screen.getByText("Сохранить изменения");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(updateProfileSpy).toHaveBeenCalledWith(
        expect.objectContaining({ first_name: "Александр" })
      );
    });

    expect(
      useToastStore
        .getState()
        .toasts.some((t) => t.message.includes("успешно обновлены"))
    ).toBe(true);
  });

  it("should switch to Security tab and validate matching passwords on change", async () => {
    const changePasswordSpy = vi.spyOn(api.account, "changePassword").mockResolvedValue({
      status: "success",
    });

    useAppStore.setState({ accountTab: "security" });
    render(<AccountManagement />);

    expect(screen.getByText("Безопасность и смена пароля")).toBeInTheDocument();

    const inputs = screen.getAllByPlaceholderText("••••••••");
    const currentPass = inputs[0];
    const newPass = inputs[1];
    const confirmPass = inputs[2];

    // Mismatched passwords
    fireEvent.change(currentPass, { target: { value: "oldPass123" } });
    fireEvent.change(newPass, { target: { value: "newPass123" } });
    fireEvent.change(confirmPass, { target: { value: "diffPass123" } });

    const submitBtn = screen.getByText("Обновить пароль");
    fireEvent.click(submitBtn);

    expect(
      useToastStore
        .getState()
        .toasts.some((t) => t.message.includes("не совпадают"))
    ).toBe(true);
    expect(changePasswordSpy).not.toHaveBeenCalled();

    // Matching passwords
    fireEvent.change(confirmPass, { target: { value: "newPass123" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(changePasswordSpy).toHaveBeenCalledWith({
        current_password: "oldPass123",
        new_password: "newPass123",
      });
    });

    expect(
      useToastStore.getState().toasts.some((t) => t.message.includes("успешно изменён"))
    ).toBe(true);
  });
});
