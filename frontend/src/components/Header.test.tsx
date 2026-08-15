/**
 * Unit tests for Header component.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { Header } from "./Header";
import { useAppStore } from "../store/useAppStore";

describe("Header component", () => {
  beforeEach(() => {
    useAppStore.setState({
      theme: "dark",
      user: null,
      currentView: "studio",
      accountTab: "history",
      jobId: null,
    });
  });

  it("should render application title, subtitle and version badge", () => {
    render(<Header />);

    expect(screen.getByText("Eidos Voice Intelligence")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Интеллектуальная транскрипция, диаризация спикеров и исполнительная аналитика встреч"
      )
    ).toBeInTheDocument();
    expect(screen.getByText("v1.0 Ready")).toBeInTheDocument();
  });

  it("should show user profile name if user is set, or loading state if null", () => {
    const { rerender } = render(<Header />);
    expect(screen.getByText("Загрузка...")).toBeInTheDocument();

    act(() => {
      useAppStore.setState({
        user: { username: "ivan_dev", full_name: "Иван Разработчик" },
      });
    });
    rerender(<Header />);
    expect(screen.getByText("Иван Разработчик")).toBeInTheDocument();
  });

  it("should toggle theme when theme button is clicked", () => {
    render(<Header />);
    const themeBtn = screen.getByRole("button", {
      name: /Переключить на светлую тему/i,
    });

    fireEvent.click(themeBtn);
    expect(useAppStore.getState().theme).toBe("light");

    const darkBtn = screen.getByRole("button", {
      name: /Переключить на тёмную тему/i,
    });
    fireEvent.click(darkBtn);
    expect(useAppStore.getState().theme).toBe("dark");
  });

  it("should switch view to account when clicking 'Личный кабинет'", () => {
    const navigateSpy = vi.fn();
    useAppStore.setState({
      currentView: "studio",
      accountTab: "history",
      navigate: navigateSpy,
    });

    render(<Header />);
    const switcher = screen.getByRole("button", {
      name: /Личный кабинет/i,
    });
    fireEvent.click(switcher);

    expect(navigateSpy).toHaveBeenCalledWith("/account/history");
  });

  it("should switch view back to studio or active job when clicking 'Студия'", () => {
    const navigateSpy = vi.fn();
    useAppStore.setState({
      currentView: "account",
      jobId: "active-job-42",
      navigate: navigateSpy,
    });

    render(<Header />);
    const switcher = screen.getByRole("button", {
      name: /Студия/i,
    });
    fireEvent.click(switcher);

    expect(navigateSpy).toHaveBeenCalledWith("/jobs/active-job-42");
  });

  it("should reset state and navigate to root when clicking main logo brand link", () => {
    const navigateSpy = vi.fn();
    useAppStore.setState({ navigate: navigateSpy });

    render(<Header />);
    const brandLink = screen.getByLabelText(/Eidos Voice Intelligence — Главная страница/i);
    fireEvent.click(brandLink);

    expect(navigateSpy).toHaveBeenCalledWith("/", { resetState: true });
  });
});
