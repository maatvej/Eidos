/**
 * Unit tests for ToastContainer component.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ToastContainer } from "./ToastContainer";
import { useToastStore } from "../store/toastStore";

describe("ToastContainer component", () => {
  beforeEach(() => {
    useToastStore.setState({ toasts: [] });
  });

  it("should render nothing when there are no active toasts", () => {
    const { container } = render(<ToastContainer />);
    expect(container.firstChild).toBeNull();
  });

  it("should render multiple toast notifications with correct styling for different types", () => {
    useToastStore.setState({
      toasts: [
        { id: "t1", message: "Успешная операция", type: "success" },
        { id: "t2", message: "Критическая ошибка", type: "error" },
        { id: "t3", message: "Предупреждение системы", type: "warning" },
        { id: "t4", message: "Информационное сообщение", type: "info" },
      ],
    });

    render(<ToastContainer />);

    expect(screen.getByText("Успешная операция")).toBeInTheDocument();
    expect(screen.getByText("Критическая ошибка")).toBeInTheDocument();
    expect(screen.getByText("Предупреждение системы")).toBeInTheDocument();
    expect(screen.getByText("Информационное сообщение")).toBeInTheDocument();

    const alerts = screen.getAllByRole("alert");
    expect(alerts).toHaveLength(4);
  });

  it("should dismiss toast when clicking close button", () => {
    useToastStore.setState({
      toasts: [{ id: "t-close", message: "Уведомление для закрытия", type: "info" }],
    });

    render(<ToastContainer />);
    expect(screen.getByText("Уведомление для закрытия")).toBeInTheDocument();

    const closeBtn = screen.getByLabelText("Закрыть уведомление");
    fireEvent.click(closeBtn);

    expect(useToastStore.getState().toasts).toHaveLength(0);
    expect(screen.queryByText("Уведомление для закрытия")).not.toBeInTheDocument();
  });
});
