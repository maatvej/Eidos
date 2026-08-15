/**
 * Unit tests for API client service and ApiError handler.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api, ApiError } from "./api";

describe("ApiError class", () => {
  it("should correctly instantiate with status, message and data", () => {
    const errorData = { detail: "Custom backend validation error" };
    const err = new ApiError(400, "Validation Failed", errorData);

    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.name).toBe("ApiError");
    expect(err.status).toBe(400);
    expect(err.message).toBe("Validation Failed");
    expect(err.data).toEqual(errorData);
  });

  it("should default data to null when omitted", () => {
    const err = new ApiError(500, "Internal Server Error");
    expect(err.status).toBe(500);
    expect(err.message).toBe("Internal Server Error");
    expect(err.data).toBeNull();
  });
});

describe("api client service", () => {
  const originalFetch = global.fetch;
  const originalLocation = window.location;

  beforeEach(() => {
    // Mock window.location
    delete (window as unknown as { location?: unknown }).location;
    (window as unknown as { location: unknown }).location = {
      pathname: "/test-path",
      search: "?query=1",
      href: "http://localhost:3000/test-path?query=1",
    };
  });

  afterEach(() => {
    global.fetch = originalFetch;
    (window as unknown as { location: unknown }).location = originalLocation;
    vi.restoreAllMocks();
  });

  describe("Authentication API (api.auth)", () => {
    it("should fetch current user profile via getCurrentUser()", async () => {
      const mockUser = {
        id: 1,
        username: "testuser",
        email: "test@example.com",
        full_name: "Test User",
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockUser,
      });

      const user = await api.auth.getCurrentUser();

      expect(global.fetch).toHaveBeenCalledWith(
        "/api/v1/auth/me",
        expect.objectContaining({
          headers: expect.objectContaining({
            Accept: "application/json",
          }),
        })
      );
      expect(user).toEqual(mockUser);
    });
  });

  describe("Transcription API (api.transcription)", () => {
    it("should get transcription job details", async () => {
      const mockJob = {
        id: "job-123",
        filename: "meeting.mp3",
        file_path: "/uploads/meeting.mp3",
        status: "COMPLETED",
        progress_percentage: 100,
        created_at: "2026-08-15T00:00:00Z",
        updated_at: "2026-08-15T00:05:00Z",
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockJob,
      });

      const job = await api.transcription.getJob("job-123");

      expect(global.fetch).toHaveBeenCalledWith(
        "/api/v1/transcription/jobs/job-123",
        expect.anything()
      );
      expect(job).toEqual(mockJob);
    });

    it("should send rename speaker request with JSON body", async () => {
      const mockResponse = {
        id: "job-123",
        status: "COMPLETED",
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      });

      const result = await api.transcription.renameSpeaker("job-123", "SPEAKER_00", "Иван");

      expect(global.fetch).toHaveBeenCalledWith(
        "/api/v1/transcription/jobs/job-123/speaker-rename",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            old_speaker_label: "SPEAKER_00",
            new_speaker_name: "Иван",
          }),
          headers: expect.objectContaining({
            "Content-Type": "application/json",
            Accept: "application/json",
          }),
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it("should construct correct audio and export URLs", () => {
      expect(api.transcription.getAudioUrl("job-777")).toBe(
        "/api/v1/transcription/jobs/job-777/audio"
      );
      expect(api.transcription.getExportUrl("job-777", "docx")).toBe(
        "/api/v1/transcription/jobs/job-777/export?export_format=docx"
      );
    });
  });

  describe("Account API (api.account)", () => {
    it("should get profile data via getProfile()", async () => {
      const mockProfile = { username: "alex", email: "alex@example.com" };
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockProfile,
      });

      const res = await api.account.getProfile();
      expect(global.fetch).toHaveBeenCalledWith("/api/v1/account/me", expect.anything());
      expect(res).toEqual(mockProfile);
    });

    it("should update profile data via updateProfile()", async () => {
      const updateData = { first_name: "Алексей", last_name: "Смирнов" };
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ ...updateData, username: "alex" }),
      });

      const res = await api.account.updateProfile(updateData);
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/v1/account/me",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify(updateData),
          headers: expect.objectContaining({
            "Content-Type": "application/json",
          }),
        })
      );
      expect(res).toEqual({ ...updateData, username: "alex" });
    });

    it("should change password via changePassword()", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ status: "success" }),
      });

      const res = await api.account.changePassword({
        current_password: "oldPassword123",
        new_password: "newPassword123",
      });

      expect(global.fetch).toHaveBeenCalledWith(
        "/api/v1/account/me",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({
            current_password: "oldPassword123",
            new_password: "newPassword123",
          }),
        })
      );
      expect(res).toEqual({ status: "success" });
    });

    it("should query paginated transcriptions with URL search parameters", async () => {
      const mockPaginated = {
        items: [],
        page: 2,
        limit: 15,
        total: 50,
        total_pages: 4,
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockPaginated,
      });

      const res = await api.account.getTranscriptions({
        page: 2,
        limit: 15,
        search: "meeting",
        sort_by: "-created_at",
      });

      expect(global.fetch).toHaveBeenCalledWith(
        "/api/v1/account/transcriptions?page=2&limit=15&search=meeting&sort_by=-created_at",
        expect.anything()
      );
      expect(res).toEqual(mockPaginated);
    });

    it("should get single transcription detail", async () => {
      const mockDetail = {
        id: "tx-1",
        title: "Совещание совета директоров",
        original_filename: "board.mp3",
        duration_seconds: 120,
        status: "COMPLETED",
        created_at: "2026-08-15T10:00:00Z",
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockDetail,
      });

      const res = await api.account.getTranscriptionDetail("tx-1");
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/v1/account/transcriptions/tx-1",
        expect.anything()
      );
      expect(res).toEqual(mockDetail);
    });

    it("should delete transcription item", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 204,
      });

      await api.account.deleteTranscription("tx-del-1");
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/v1/account/transcriptions/tx-del-1",
        expect.objectContaining({
          method: "DELETE",
        })
      );
    });
  });

  describe("Error Handling and Special Responses", () => {
    it("should redirect to login on 401 Unauthorized", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        status: 401,
        ok: false,
      });

      await expect(api.auth.getCurrentUser()).rejects.toThrow(ApiError);
      await expect(api.auth.getCurrentUser()).rejects.toThrow("Unauthorized");
      expect(window.location.href).toBe(
        "/accounts/login/?next=%2Ftest-path%3Fquery%3D1"
      );
    });

    it("should throw ApiError with backend detail on 400/422 errors", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        status: 422,
        ok: false,
        statusText: "Unprocessable Entity",
        json: async () => ({ detail: "Invalid speaker name" }),
      });

      await expect(
        api.transcription.renameSpeaker("job-1", "A", "")
      ).rejects.toThrow("Invalid speaker name");
    });

    it("should fallback to statusText if response json parsing fails", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        status: 500,
        ok: false,
        statusText: "Internal Server Error",
        json: async () => {
          throw new Error("Invalid JSON");
        },
      });

      await expect(api.account.getProfile()).rejects.toThrow(
        "HTTP Error 500: Internal Server Error"
      );
    });
  });
});
