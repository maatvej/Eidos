/**
 * Unit tests for FileUploadDropzone component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { FileUploadDropzone } from "./FileUploadDropzone";
import { useAppStore } from "../store/useAppStore";
import { useToastStore } from "../store/toastStore";

describe("FileUploadDropzone component", () => {
  let mockXHR: {
    open: ReturnType<typeof vi.fn>;
    send: ReturnType<typeof vi.fn>;
    upload: { onprogress: ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) | null };
    status: number;
    responseText: string;
    onload: (() => void) | null;
    onerror: (() => void) | null;
  };

  beforeEach(() => {
    useAppStore.setState({
      jobId: null,
      status: "IDLE",
      progress: 0,
      errorMessage: null,
    });
    useToastStore.setState({ toasts: [] });

    mockXHR = {
      open: vi.fn(),
      send: vi.fn(),
      upload: { onprogress: null },
      status: 202,
      responseText: JSON.stringify({ job_id: "new-upload-job-123" }),
      onload: null,
      onerror: null,
    };

    // Stub XMLHttpRequest
    window.XMLHttpRequest = vi.fn().mockImplementation(() => mockXHR) as unknown as typeof XMLHttpRequest;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should render upload instructions, dropzone UI and supported extensions", () => {
    render(<FileUploadDropzone />);

    expect(screen.getByText("Загрузить аудиозапись встречи")).toBeInTheDocument();
    expect(
      screen.getByText("Перетащите сюда файл или нажмите для выбора")
    ).toBeInTheDocument();
    expect(screen.getByText(/wav/i)).toBeInTheDocument();
    expect(screen.getByText(/mp3/i)).toBeInTheDocument();
    expect(screen.getByText(/m4a/i)).toBeInTheDocument();
  });

  it("should reject unsupported file extensions and display error toast", () => {
    render(<FileUploadDropzone />);

    const badFile = new File(["dummy"], "document.pdf", { type: "application/pdf" });
    const dropzone = screen.getByRole("button", {
      name: /Загрузить аудиозапись встречи/i,
    });

    fireEvent.drop(dropzone, {
      dataTransfer: { files: [badFile] },
    });

    const toasts = useToastStore.getState().toasts;
    expect(toasts.some((t) => t.type === "error" && t.message.includes(".pdf"))).toBe(true);
    expect(mockXHR.send).not.toHaveBeenCalled();
  });

  it("should reject file exceeding 500 MB limit", () => {
    render(<FileUploadDropzone />);

    const hugeFile = new File(["x"], "huge_record.mp3", { type: "audio/mp3" });
    Object.defineProperty(hugeFile, "size", { value: 600 * 1024 * 1024 });

    const dropzone = screen.getByRole("button", {
      name: /Загрузить аудиозапись встречи/i,
    });

    fireEvent.drop(dropzone, {
      dataTransfer: { files: [hugeFile] },
    });

    const toasts = useToastStore.getState().toasts;
    expect(toasts.some((t) => t.type === "error" && t.message.includes("500 МБ"))).toBe(true);
    expect(mockXHR.send).not.toHaveBeenCalled();
  });

  it("should successfully upload valid audio file and navigate to job", () => {
    const navigateSpy = vi.fn();
    useAppStore.setState({ navigate: navigateSpy });

    render(<FileUploadDropzone />);

    const validFile = new File(["audio data"], "interview.wav", { type: "audio/wav" });
    const dropzone = screen.getByRole("button", {
      name: /Загрузить аудиозапись встречи/i,
    });

    fireEvent.drop(dropzone, {
      dataTransfer: { files: [validFile] },
    });

    expect(mockXHR.open).toHaveBeenCalledWith("POST", "/api/v1/transcription/upload", true);
    expect(mockXHR.send).toHaveBeenCalled();

    // Trigger upload progress
    act(() => {
      mockXHR.upload.onprogress?.({ lengthComputable: true, loaded: 50, total: 100 });
    });

    // Complete upload
    act(() => {
      mockXHR.status = 202;
      mockXHR.onload?.();
    });

    expect(useAppStore.getState().jobId).toBe("new-upload-job-123");
    expect(useAppStore.getState().status).toBe("LOADING");
    expect(navigateSpy).toHaveBeenCalledWith("/jobs/new-upload-job-123");
  });

  it("should handle server error response gracefully", () => {
    render(<FileUploadDropzone />);

    const validFile = new File(["audio data"], "fail.mp3", { type: "audio/mp3" });
    const dropzone = screen.getByRole("button", {
      name: /Загрузить аудиозапись встречи/i,
    });

    fireEvent.drop(dropzone, {
      dataTransfer: { files: [validFile] },
    });

    act(() => {
      mockXHR.status = 500;
      mockXHR.onload?.();
    });

    expect(useAppStore.getState().status).toBe("ERROR");
    expect(useAppStore.getState().errorMessage).toContain("500");
  });

  it("should handle network failure on upload", () => {
    render(<FileUploadDropzone />);

    const validFile = new File(["audio data"], "network_err.mp3", { type: "audio/mp3" });
    const dropzone = screen.getByRole("button", {
      name: /Загрузить аудиозапись встречи/i,
    });

    fireEvent.drop(dropzone, {
      dataTransfer: { files: [validFile] },
    });

    act(() => {
      mockXHR.onerror?.();
    });

    expect(useAppStore.getState().status).toBe("ERROR");
    expect(useAppStore.getState().errorMessage).toBe("Сетевой сбой при отправке файла на сервер.");
  });
});
