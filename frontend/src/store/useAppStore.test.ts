/**
 * Unit tests for Centralized Application Store (useAppStore) and StorageHelper.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useAppStore, StorageHelper } from "./useAppStore";
import { TranscriptionJobEntity, TranscriptionResult, UserProfile } from "../types";

describe("StorageHelper", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  it("should save and retrieve active job ID", () => {
    StorageHelper.saveActiveJob("job-abc-123");
    expect(StorageHelper.getActiveJob()).toBe("job-abc-123");
    expect(sessionStorage.getItem(StorageHelper.ACTIVE_JOB_KEY)).toBe("job-abc-123");
    expect(localStorage.getItem(StorageHelper.ACTIVE_JOB_KEY)).toBe("job-abc-123");
  });

  it("should do nothing if null/empty jobId passed to saveActiveJob", () => {
    StorageHelper.saveActiveJob(null);
    expect(StorageHelper.getActiveJob()).toBeNull();
  });

  it("should clear active job ID and state", () => {
    StorageHelper.saveActiveJob("job-abc-123");
    sessionStorage.setItem(StorageHelper.JOB_STATE_KEY, "{}");
    localStorage.setItem(StorageHelper.JOB_STATE_KEY, "{}");

    StorageHelper.clearActiveJob();
    expect(StorageHelper.getActiveJob()).toBeNull();
    expect(sessionStorage.getItem(StorageHelper.JOB_STATE_KEY)).toBeNull();
  });

  it("should save and get job state snapshot", () => {
    const snapshot = {
      jobId: "job-xyz",
      status: "SUCCESS" as const,
      progress: 100,
      stepMessage: "Готово",
      transcript: { utterances: [] },
      errorMessage: null,
      currentTime: 12.5,
      initialAudioTime: 12.5,
      initialSearchQuery: "важно",
      savedAt: Date.now(),
    };

    StorageHelper.saveJobState(snapshot);

    const retrieved = StorageHelper.getSavedJobState("job-xyz");
    expect(retrieved).not.toBeNull();
    expect(retrieved?.jobId).toBe("job-xyz");
    expect(retrieved?.progress).toBe(100);
    expect(retrieved?.initialSearchQuery).toBe("важно");
  });

  it("should return null for getSavedJobState when no match found", () => {
    expect(StorageHelper.getSavedJobState("non-existent")).toBeNull();
  });

  it("should save and get last view", () => {
    StorageHelper.saveLastView("account");
    expect(StorageHelper.getLastView()).toBe("account");

    StorageHelper.saveLastView("studio");
    expect(StorageHelper.getLastView()).toBe("studio");
  });
});

describe("useAppStore", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    useAppStore.setState({
      theme: "dark",
      user: null,
      currentView: "studio",
      currentRoute: "/",
      accountTab: "history",
      jobId: null,
      status: "IDLE",
      progress: 0,
      stepMessage: "",
      transcript: null,
      errorMessage: null,
      currentTime: 0,
      initialAudioTime: 0,
      initialSearchQuery: "",
    });
    sessionStorage.clear();
    localStorage.clear();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  describe("Theme management", () => {
    it("should set theme and update html attributes", () => {
      useAppStore.getState().setTheme("light");
      expect(useAppStore.getState().theme).toBe("light");
      expect(document.documentElement.getAttribute("data-theme")).toBe("light");
      expect(document.documentElement.classList.contains("dark")).toBe(false);
      expect(localStorage.getItem("eidos_theme")).toBe("light");

      useAppStore.getState().setTheme("dark");
      expect(useAppStore.getState().theme).toBe("dark");
      expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
      expect(document.documentElement.classList.contains("dark")).toBe(true);
      expect(localStorage.getItem("eidos_theme")).toBe("dark");
    });

    it("should toggle theme between dark and light", () => {
      useAppStore.setState({ theme: "dark" });
      useAppStore.getState().toggleTheme();
      expect(useAppStore.getState().theme).toBe("light");

      useAppStore.getState().toggleTheme();
      expect(useAppStore.getState().theme).toBe("dark");
    });
  });

  describe("User and View navigation", () => {
    it("should set user profile", () => {
      const user: UserProfile = { username: "maria", full_name: "Мария Иванова" };
      useAppStore.getState().setUser(user);
      expect(useAppStore.getState().user).toEqual(user);
    });

    it("should set view and update storage", () => {
      useAppStore.getState().setView("account", false);
      expect(useAppStore.getState().currentView).toBe("account");
      expect(StorageHelper.getLastView()).toBe("account");
    });

    it("should set account tab and switch view to account", () => {
      useAppStore.getState().setAccountTab("profile", false);
      expect(useAppStore.getState().accountTab).toBe("profile");
      expect(useAppStore.getState().currentView).toBe("account");
    });

    it("should set current time", () => {
      useAppStore.getState().setCurrentTime(45.2);
      expect(useAppStore.getState().currentTime).toBe(45.2);
    });
  });

  describe("Job state management and Speaker renaming", () => {
    it("should update job state and persist to storage when jobId is present", () => {
      useAppStore.getState().setJobState({
        jobId: "job-999",
        status: "PROCESSING" as unknown as "LOADING",
        progress: 40,
        stepMessage: "Распознавание речи...",
      });

      const state = useAppStore.getState();
      expect(state.jobId).toBe("job-999");
      expect(state.progress).toBe(40);
      expect(StorageHelper.getActiveJob()).toBe("job-999");
    });

    it("should reset job state and clear active job in storage", () => {
      useAppStore.getState().setJobState({
        jobId: "job-999",
        status: "SUCCESS",
        progress: 100,
      });

      useAppStore.getState().resetJobState();

      const state = useAppStore.getState();
      expect(state.jobId).toBeNull();
      expect(state.status).toBe("IDLE");
      expect(state.progress).toBe(0);
      expect(StorageHelper.getActiveJob()).toBeNull();
    });

    it("should rename speaker in transcript state", () => {
      const sampleTranscript: TranscriptionResult = {
        utterances: [
          {
            id: "utt-1",
            speaker: "SPEAKER_00",
            start: 0,
            end: 5,
            text: "Привет всем!",
            words: [
              { word: "Привет", start: 0, end: 1, speaker: "SPEAKER_00" },
              { word: "всем!", start: 1.2, end: 2, speaker: "SPEAKER_00" },
            ],
          },
          {
            id: "utt-2",
            speaker: "SPEAKER_01",
            start: 5.5,
            end: 8,
            text: "Здравствуйте!",
            words: [{ word: "Здравствуйте!", start: 5.5, end: 7, speaker: "SPEAKER_01" }],
          },
        ],
      };

      useAppStore.setState({ transcript: sampleTranscript });
      useAppStore.getState().renameSpeakerInState("SPEAKER_00", "Алексей");

      const updated = useAppStore.getState().transcript;
      expect(updated?.utterances[0].speaker).toBe("Алексей");
      expect(updated?.utterances[0].words?.[0].speaker).toBe("Алексей");
      expect(updated?.utterances[1].speaker).toBe("SPEAKER_01");
    });
  });

  describe("Routing and Navigation", () => {
    it("should resolve account sub-routes", async () => {
      await useAppStore.getState().resolveCurrentRoute("/account/security");
      expect(useAppStore.getState().currentView).toBe("account");
      expect(useAppStore.getState().accountTab).toBe("security");

      await useAppStore.getState().resolveCurrentRoute("/account/profile");
      expect(useAppStore.getState().accountTab).toBe("profile");
    });

    it("should resolve root route and reset job state", async () => {
      useAppStore.setState({ jobId: "job-1", status: "SUCCESS" });
      await useAppStore.getState().resolveCurrentRoute("/");
      expect(useAppStore.getState().currentView).toBe("studio");
      expect(useAppStore.getState().jobId).toBeNull();
    });

    it("should navigate with replace and resetState options", async () => {
      await useAppStore.getState().navigate("/account/history", { replace: true, resetState: true });
      expect(useAppStore.getState().currentView).toBe("account");
      expect(useAppStore.getState().accountTab).toBe("history");
    });
  });

  describe("hydrateJob", () => {
    it("should return false if jobId is empty", async () => {
      const result = await useAppStore.getState().hydrateJob("");
      expect(result).toBe(false);
    });

    it("should successfully hydrate completed job from /api/v1/transcription/jobs/:id", async () => {
      const mockResult: TranscriptionResult = {
        utterances: [{ id: "1", speaker: "Иван", start: 0, end: 10, text: "Добрый день." }],
        analysis: { title: "Совещание" },
      };

      const mockJob: TranscriptionJobEntity = {
        id: "job-100",
        filename: "test.mp3",
        file_path: "/path/test.mp3",
        status: "COMPLETED",
        progress_percentage: 100,
        result: mockResult,
        created_at: "2026-08-15T00:00:00Z",
        updated_at: "2026-08-15T00:05:00Z",
      };

      global.fetch = vi.fn().mockImplementation(async (url: string) => {
        if (url.includes("/api/v1/transcription/jobs/job-100")) {
          return {
            ok: true,
            status: 200,
            json: async () => mockJob,
          };
        }
        return { ok: false, status: 404 };
      });

      const success = await useAppStore.getState().hydrateJob("job-100", { seekTime: 5 });
      expect(success).toBe(true);

      const state = useAppStore.getState();
      expect(state.status).toBe("SUCCESS");
      expect(state.progress).toBe(100);
      expect(state.transcript).toEqual(mockResult);
      expect(state.currentTime).toBe(5);
    });

    it("should handle failed job status from endpoint", async () => {
      global.fetch = vi.fn().mockImplementation(async (url: string) => {
        if (url.includes("/api/v1/transcription/jobs/job-failed")) {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              id: "job-failed",
              status: "FAILED",
              error_message: "Формат файла поврежден",
            }),
          };
        }
        return { ok: false, status: 404 };
      });

      const success = await useAppStore.getState().hydrateJob("job-failed");
      expect(success).toBe(false);

      const state = useAppStore.getState();
      expect(state.status).toBe("ERROR");
      expect(state.errorMessage).toBe("Формат файла поврежден");
    });

    it("should handle cancelled job status from endpoint", async () => {
      global.fetch = vi.fn().mockImplementation(async (url: string) => {
        if (url.includes("/api/v1/transcription/jobs/job-canc")) {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              id: "job-canc",
              status: "CANCELLED",
            }),
          };
        }
        return { ok: false, status: 404 };
      });

      const success = await useAppStore.getState().hydrateJob("job-canc");
      expect(success).toBe(false);

      const state = useAppStore.getState();
      expect(state.status).toBe("ERROR");
      expect(state.errorMessage).toBe("Обработка задачи была отменена.");
    });

    it("should fallback to account transcriptions endpoint and parse synthesized text", async () => {
      global.fetch = vi.fn().mockImplementation(async (url: string) => {
        if (url.includes("/api/v1/transcription/jobs/tx-account-1")) {
          return { ok: false, status: 404 };
        }
        if (url.includes("/api/v1/account/transcriptions/tx-account-1")) {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              id: "tx-account-1",
              title: "Интервью с клиентом",
              status: "COMPLETED",
              transcription_text: "Интервьюер: Здравствуйте!\n\nРеспондент: Добрый день!",
              duration_seconds: 60,
              language: "ru",
            }),
          };
        }
        return { ok: false, status: 404 };
      });

      const success = await useAppStore.getState().hydrateJob("tx-account-1");
      expect(success).toBe(true);

      const state = useAppStore.getState();
      expect(state.status).toBe("SUCCESS");
      expect(state.transcript?.utterances).toHaveLength(2);
      expect(state.transcript?.utterances[0].speaker).toBe("Интервьюер");
      expect(state.transcript?.utterances[0].text).toBe("Здравствуйте!");
      expect(state.transcript?.utterances[1].speaker).toBe("Респондент");
    });

    it("should fallback to cached storage snapshot if backend endpoints return 404", async () => {
      const mockResult: TranscriptionResult = {
        utterances: [{ id: "cached-1", speaker: "Спикер", start: 0, end: 10, text: "Кэш" }],
      };

      StorageHelper.saveJobState({
        jobId: "job-cached",
        status: "SUCCESS",
        progress: 100,
        stepMessage: "Стенограмма готова",
        transcript: mockResult,
        errorMessage: null,
        currentTime: 0,
        initialAudioTime: 0,
        initialSearchQuery: "",
        savedAt: Date.now(),
      });

      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 });

      const success = await useAppStore.getState().hydrateJob("job-cached");
      expect(success).toBe(true);

      const state = useAppStore.getState();
      expect(state.status).toBe("SUCCESS");
      expect(state.transcript).toEqual(mockResult);
    });

    it("should set error state if hydration fails and no cache exists", async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error("Network Error"));

      const success = await useAppStore.getState().hydrateJob("job-nonexistent");
      expect(success).toBe(false);

      const state = useAppStore.getState();
      expect(state.status).toBe("ERROR");
      expect(state.errorMessage).toBe("Сетевой сбой при восстановлении данных задачи.");
    });
  });
});
