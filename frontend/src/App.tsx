import React, { useEffect } from "react";
import { Header } from "./components/Header";
import { FileUploadDropzone } from "./components/FileUploadDropzone";
import { ExecutiveIntelligenceCard } from "./components/ExecutiveIntelligenceCard";
import { TranscriptPlayer } from "./components/TranscriptPlayer";
import { AccountManagement } from "./components/AccountManagement";
import { ToastContainer } from "./components/ToastContainer";
import { useAppStore, StorageHelper } from "./store/useAppStore";
import { showToast } from "./store/toastStore";
import { api } from "./services/api";

export const App: React.FC = () => {
  const {
    currentView,
    jobId,
    status,
    setUser,
    setView,
    setCurrentRoute,
    setJobState,
    hydrateJob,
    resetJobState,
  } = useAppStore();

  // Load User Profile on mount
  useEffect(() => {
    api.auth
      .getCurrentUser()
      .then((user) => setUser(user))
      .catch((err) => {
        console.error("[Auth] Error fetching current user:", err);
      });
  }, [setUser]);

  // Client-Side Routing and URL Synchronization
  useEffect(() => {
    const handlePopState = () => {
      resolveRoute(window.location.pathname, window.location.search);
    };

    window.addEventListener("popstate", handlePopState);
    resolveRoute(window.location.pathname, window.location.search);

    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const resolveRoute = (pathname: string, search: string) => {
    setCurrentRoute(pathname + search);
    const searchParams = new URLSearchParams(search);

    if (pathname.startsWith("/account")) {
      setView("account", false);
      return;
    }

    const jobMatch = pathname.match(/^\/(?:jobs|transcriptions|job|transcription)\/([^/?#]+)/);
    if (jobMatch && jobMatch[1]) {
      setView("studio", false);
      const targetJobId = decodeURIComponent(jobMatch[1]);
      hydrateJob(targetJobId, {
        seekTime: searchParams.get("t") ? parseFloat(searchParams.get("t")!) : undefined,
        searchQuery: searchParams.get("q") || undefined,
      });
      return;
    }

    // Default studio route / or /studio or /dashboard
    setView("studio", false);
    if (pathname === "/" || pathname === "/studio" || pathname === "/dashboard") {
      const activeJobId = StorageHelper.getActiveJob();
      if (!activeJobId) {
        resetJobState();
      }
    }
  };

  // Real-time SSE Connection for Transcription Progress Updates
  useEffect(() => {
    if (!jobId || status !== "LOADING") {
      return;
    }

    const sse = new EventSource(`/api/v1/events/sse/${jobId}`);

    sse.addEventListener("progress", (e) => {
      try {
        const data = JSON.parse(e.data);
        setJobState({
          progress: data.progress,
          stepMessage: data.step,
          status: "LOADING",
        });
      } catch (err) {
        console.error("[SSE] Failed to parse progress payload:", err);
      }
    });

    sse.addEventListener("complete", async () => {
      sse.close();
      try {
        const jobEntity = await api.transcription.getJob(jobId);
        const statusUpper = (jobEntity.status || "").toUpperCase();

        if (statusUpper === "COMPLETED" && jobEntity.result) {
          setJobState({
            jobId: jobEntity.id || jobId,
            status: "SUCCESS",
            progress: 100,
            stepMessage: "Стенограмма готова",
            transcript: jobEntity.result,
            errorMessage: null,
          });
          showToast("Транскрипция и аналитика успешно сформированы!", "success");
        } else if (statusUpper === "FAILED") {
          setJobState({
            jobId: jobEntity.id || jobId,
            status: "ERROR",
            progress: 0,
            errorMessage: jobEntity.error_message || "Ошибка при выполнении расшифровки аудиофайла.",
          });
          showToast(jobEntity.error_message || "Ошибка обработки аудиофайла", "error");
        } else {
          await hydrateJob(jobId);
        }
      } catch (err) {
        console.error("[SSE Complete] Error loading final results:", err);
        await hydrateJob(jobId);
      }
    });

    sse.addEventListener("error", () => {
      sse.close();
    });

    return () => {
      sse.close();
    };
  }, [jobId, status, setJobState, hydrateJob]);

  return (
    <div className="max-w-[1440px] mx-auto p-4 md:p-6 lg:p-8 min-h-screen flex flex-col">
      <Header />

      {currentView === "studio" && (
        <main className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-1 items-start" role="main">
          {/* Sidebar / Upload Panel */}
          <aside className="lg:col-span-4" aria-label="Панель загрузки файлов">
            <FileUploadDropzone />
          </aside>

          {/* Main Results Panel */}
          <section className="lg:col-span-8 flex flex-col gap-6" aria-label="Панель результатов транскрипции и аналитики">
            <ExecutiveIntelligenceCard />
            <TranscriptPlayer />
          </section>
        </main>
      )}

      {currentView === "account" && (
        <section className="py-2 flex-1" aria-label="Раздел управления аккаунтом и истории транскрипций">
          <AccountManagement />
        </section>
      )}

      <ToastContainer />
    </div>
  );
};
