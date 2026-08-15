/**
 * Unit tests for toast notifications Zustand store.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useToastStore, showToast } from "./toastStore";

describe("useToastStore", () => {
  beforeEach(() => {
    useToastStore.setState({ toasts: [] });
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should initialize with an empty toast list", () => {
    expect(useToastStore.getState().toasts).toEqual([]);
  });

  it("should add toast notification with default type and duration", () => {
    useToastStore.getState().addToast("Тестовое сообщение");

    const toasts = useToastStore.getState().toasts;
    expect(toasts).toHaveLength(1);
    expect(toasts[0].message).toBe("Тестовое сообщение");
    expect(toasts[0].type).toBe("info");
    expect(toasts[0].duration).toBe(4000);
    expect(toasts[0].id).toBeDefined();
  });

  it("should add toast notification with custom type and duration", () => {
    useToastStore.getState().addToast("Ошибка сохранения", "error", 6000);

    const toasts = useToastStore.getState().toasts;
    expect(toasts).toHaveLength(1);
    expect(toasts[0].message).toBe("Ошибка сохранения");
    expect(toasts[0].type).toBe("error");
    expect(toasts[0].duration).toBe(6000);
  });

  it("should auto-remove toast after specified duration", () => {
    useToastStore.getState().addToast("Временное сообщение", "success", 3000);
    expect(useToastStore.getState().toasts).toHaveLength(1);

    vi.advanceTimersByTime(2999);
    expect(useToastStore.getState().toasts).toHaveLength(1);

    vi.advanceTimersByTime(2);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it("should not auto-remove toast if duration is 0", () => {
    useToastStore.getState().addToast("Постоянное сообщение", "warning", 0);
    expect(useToastStore.getState().toasts).toHaveLength(1);

    vi.advanceTimersByTime(10000);
    expect(useToastStore.getState().toasts).toHaveLength(1);
  });

  it("should remove toast manually via removeToast(id)", () => {
    useToastStore.getState().addToast("Первое", "info", 0);
    useToastStore.getState().addToast("Второе", "info", 0);

    const toasts = useToastStore.getState().toasts;
    expect(toasts).toHaveLength(2);

    const firstId = toasts[0].id;
    useToastStore.getState().removeToast(firstId);

    const remaining = useToastStore.getState().toasts;
    expect(remaining).toHaveLength(1);
    expect(remaining[0].message).toBe("Второе");
  });

  it("showToast helper should invoke addToast on the store", () => {
    showToast("Вызов через showToast", "success", 2500);

    const toasts = useToastStore.getState().toasts;
    expect(toasts).toHaveLength(1);
    expect(toasts[0].message).toBe("Вызов через showToast");
    expect(toasts[0].type).toBe("success");
    expect(toasts[0].duration).toBe(2500);
  });
});
