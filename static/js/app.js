// filename: static/js/app.js
/**
 * Frontend Application Bootstrapper & Real-Time Progress Synchronization.
 * Manages Server-Sent Events (SSE), reactive state store synchronization,
 * declarative URL routing, state hydration, view switching, and theme management.
 */
import {
  globalStore,
  showToast,
  toggleTheme,
  applyTheme,
  StorageHelper,
  hydrateJob,
  resetJobState,
} from "./store.js";
import { router } from "./router.js";

import "./components/FileUploadDropzone.js";
import "./components/ExecutiveIntelligenceCard.js";
import "./components/TranscriptPlayer.js";
import "./components/AccountManagement.js";

let sseEventSource = null;
let currentConnectedJobId = null;

// Initialize user profile display
async function loadUserProfile() {
  const userDisplayNameEl = document.getElementById("userDisplayName");
  try {
    const response = await fetch("/api/v1/auth/me");
    if (response.ok) {
      const user = await response.json();
      globalStore.setState({ user });
      if (userDisplayNameEl) {
        userDisplayNameEl.textContent = user.username || user.email;
      }
    } else if (response.status === 401) {
      const returnUrl = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = `/accounts/login/?next=${returnUrl}`;
    }
  } catch (err) {
    console.error("[Auth] Failed to load current user profile:", err);
  }
}

loadUserProfile();

// Workspace Elements
const viewToggleBtn = document.getElementById("viewToggleBtn");
const studioWorkspace = document.getElementById("studioWorkspace");
const accountWorkspace = document.getElementById("accountWorkspace");
const viewToggleText = document.getElementById("viewToggleText");

/**
 * Cleanly transitions between Studio and Account views
 * @param {"studio" | "account"} targetView
 */
function switchView(targetView) {
  const isAccount = targetView === "account";

  if (studioWorkspace && accountWorkspace) {
    if (isAccount) {
      studioWorkspace.style.display = "none";
      accountWorkspace.style.display = "block";
    } else {
      studioWorkspace.style.display = "grid";
      accountWorkspace.style.display = "none";
    }
  }

  if (viewToggleBtn) {
    viewToggleBtn.setAttribute("aria-pressed", isAccount ? "true" : "false");
    viewToggleBtn.setAttribute(
      "aria-label",
      isAccount ? "Вернуться на Главную (Студия)" : "Переключить в Личный кабинет"
    );
    if (viewToggleBtn.tagName === "A") {
      viewToggleBtn.setAttribute("href", isAccount ? "/" : "/account");
    }
  }

  if (viewToggleText) {
    viewToggleText.textContent = isAccount ? "Студия" : "Личный кабинет";
  }

  StorageHelper.saveLastView(targetView);
  globalStore.setState({ currentView: targetView });
}

// View Switcher Click Handler with Router Integration
if (viewToggleBtn) {
  viewToggleBtn.addEventListener("click", (e) => {
    e.preventDefault();
    if (globalStore.state.currentView === "account") {
      router.navigate("/");
    } else {
      router.navigate("/account/history");
    }
  });
}

/**
 * Update Theme Toggle Button UI (Icons & Labels)
 * @param {"dark" | "light"} theme
 */
function updateThemeToggleUI(theme) {
  const themeBtn = document.getElementById("themeToggleBtn");
  const iconSlot = document.getElementById("themeIconSlot");
  if (!themeBtn) return;

  const isDark = theme === "dark";
  themeBtn.setAttribute("aria-pressed", isDark ? "true" : "false");
  themeBtn.setAttribute(
    "aria-label",
    isDark ? "Переключить на светлую тему" : "Переключить на тёмную тему"
  );
  themeBtn.setAttribute(
    "title",
    isDark ? "Переключить на светлую тему" : "Переключить на тёмную тему"
  );

  if (iconSlot) {
    if (isDark) {
      // Sun icon for dark mode (to switch to light)
      iconSlot.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="5"></circle>
          <line x1="12" y1="1" x2="12" y2="3"></line>
          <line x1="12" y1="21" x2="12" y2="23"></line>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
          <line x1="1" y1="12" x2="3" y2="12"></line>
          <line x1="21" y1="12" x2="23" y2="12"></line>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
        </svg>
      `;
    } else {
      // Moon icon for light mode (to switch to dark)
      iconSlot.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>
      `;
    }
  }
}

// Initial theme apply
applyTheme(globalStore.state.theme, false);
updateThemeToggleUI(globalStore.state.theme);

// Theme Switcher Click Handler
const themeBtn = document.getElementById("themeToggleBtn");
if (themeBtn) {
  themeBtn.addEventListener("click", () => {
    toggleTheme();
  });
}

// Watch theme changes in store
globalStore.subscribe((state) => {
  updateThemeToggleUI(state.theme);
}, ["theme"]);

// Configure Client-Side Routes
router
  // Main Studio & Dashboard Routes (Clean Empty State waiting for file upload)
  .addRoute("/", async () => {
    switchView("studio");
    globalStore.setState({ currentRoute: "/" });
    resetJobState();
  })
  .addRoute("/studio", async () => {
    switchView("studio");
    globalStore.setState({ currentRoute: "/studio" });
    resetJobState();
  })
  .addRoute("/dashboard", async () => {
    switchView("studio");
    globalStore.setState({ currentRoute: "/dashboard" });
    resetJobState();
  })

  // Deep Links to Specific Job / Transcription (Uploading / Completed State)
  .addRoute("/job/:jobId", async (context) => {
    switchView("studio");
    const jobId = context.params.jobId;
    globalStore.setState({ currentRoute: `/job/${jobId}` });
    await hydrateJob(jobId, {
      seekTime: context.query.t,
      searchQuery: context.query.q,
    });
  })
  .addRoute("/jobs/:jobId", async (context) => {
    switchView("studio");
    const jobId = context.params.jobId;
    globalStore.setState({ currentRoute: `/jobs/${jobId}` });
    await hydrateJob(jobId, {
      seekTime: context.query.t,
      searchQuery: context.query.q,
    });
  })
  .addRoute("/transcription/:jobId", async (context) => {
    switchView("studio");
    const jobId = context.params.jobId;
    globalStore.setState({ currentRoute: `/transcription/${jobId}` });
    await hydrateJob(jobId, {
      seekTime: context.query.t,
      searchQuery: context.query.q,
    });
  })
  .addRoute("/transcriptions/:jobId", async (context) => {
    switchView("studio");
    const jobId = context.params.jobId;
    globalStore.setState({ currentRoute: `/transcriptions/${jobId}` });
    await hydrateJob(jobId, {
      seekTime: context.query.t,
      searchQuery: context.query.q,
    });
  })

  // Account Management & History Routes
  .addRoute("/account", (context) => {
    switchView("account");
    globalStore.setState({ currentRoute: "/account" });
    const accountEl = document.querySelector("account-management");
    if (accountEl && typeof accountEl.syncFromRoute === "function") {
      accountEl.syncFromRoute("history", context.query);
    }
  })
  .addRoute("/account/history", (context) => {
    switchView("account");
    globalStore.setState({ currentRoute: "/account/history" });
    const accountEl = document.querySelector("account-management");
    if (accountEl && typeof accountEl.syncFromRoute === "function") {
      accountEl.syncFromRoute("history", context.query);
    }
  })
  .addRoute("/account/profile", (context) => {
    switchView("account");
    globalStore.setState({ currentRoute: "/account/profile" });
    const accountEl = document.querySelector("account-management");
    if (accountEl && typeof accountEl.syncFromRoute === "function") {
      accountEl.syncFromRoute("profile", context.query);
    }
  })
  .addRoute("/account/security", (context) => {
    switchView("account");
    globalStore.setState({ currentRoute: "/account/security" });
    const accountEl = document.querySelector("account-management");
    if (accountEl && typeof accountEl.syncFromRoute === "function") {
      accountEl.syncFromRoute("profile", context.query);
    }
  })
  .addRoute("/account/:subTab", (context) => {
    switchView("account");
    globalStore.setState({ currentRoute: `/account/${context.params.subTab}` });
    const accountEl = document.querySelector("account-management");
    if (accountEl && typeof accountEl.syncFromRoute === "function") {
      accountEl.syncFromRoute(context.params.subTab, context.query);
    }
  });

// Fallback Route Handler
router.setNotFoundHandler((pathname, context) => {
  if (pathname.startsWith("/account")) {
    router.navigate("/account/history", { replace: true });
  } else {
    router.navigate("/", { replace: true });
  }
});

// Initialize the Router on application startup
router.init();

// Subscribe to store state changes for SSE progress streaming
globalStore.subscribe((state) => {
  if (state.jobId && state.status === "LOADING") {
    if (!sseEventSource || currentConnectedJobId !== state.jobId) {
      connectSSE(state.jobId);
    }
  } else if (state.status !== "LOADING" && sseEventSource) {
    sseEventSource.close();
    sseEventSource = null;
    currentConnectedJobId = null;
  }
}, ["jobId", "status"]);

/**
 * Establishes Server-Sent Events (SSE) connection for real-time transcription progress updates.
 * @param {string} jobId - Active job UUID
 */
function connectSSE(jobId) {
  if (sseEventSource) {
    sseEventSource.close();
    sseEventSource = null;
  }

  currentConnectedJobId = jobId;
  sseEventSource = new EventSource(`/api/v1/events/sse/${jobId}`);

  sseEventSource.addEventListener("progress", (e) => {
    try {
      const data = JSON.parse(e.data);
      globalStore.setState({
        progress: data.progress,
        stepMessage: data.step,
        status: "LOADING",
      });
    } catch (err) {
      console.error("[SSE] Failed to parse progress payload:", err);
    }
  });

  sseEventSource.addEventListener("complete", async () => {
    if (sseEventSource) {
      sseEventSource.close();
      sseEventSource = null;
      currentConnectedJobId = null;
    }

    // Fetch complete result payload
    try {
      const res = await fetch(`/api/v1/transcription/jobs/${jobId}`);
      if (res.ok) {
        const jobEntity = await res.json();
        const statusUpper = (jobEntity.status || "").toUpperCase();

        if (statusUpper === "COMPLETED" && jobEntity.result) {
          globalStore.setState({
            jobId: jobEntity.id || jobId,
            status: "SUCCESS",
            progress: 100,
            stepMessage: "Стенограмма готова",
            transcript: jobEntity.result,
            errorMessage: null,
          });
          showToast("Транскрипция и аналитика успешно сформированы!", "success");
        } else if (statusUpper === "FAILED") {
          globalStore.setState({
            jobId: jobEntity.id || jobId,
            status: "ERROR",
            progress: 0,
            errorMessage: jobEntity.error_message || "Ошибка при выполнении расшифровки аудиофайла.",
          });
          showToast(jobEntity.error_message || "Ошибка обработки аудиофайла", "error");
        } else if (statusUpper === "CANCELLED") {
          globalStore.setState({
            jobId: jobEntity.id || jobId,
            status: "ERROR",
            progress: 0,
            errorMessage: "Обработка задачи была отменена.",
          });
          showToast("Задача отменена", "warning");
        } else {
          await hydrateJob(jobId);
        }
      } else {
        throw new Error(`HTTP ${res.status}`);
      }
    } catch (err) {
      console.error("[SSE Complete] Failed to fetch final job results:", err);
      const hydrated = await hydrateJob(jobId);
      if (!hydrated) {
        globalStore.setState({
          status: "ERROR",
          errorMessage: "Не удалось загрузить финальные результаты стенограммы.",
        });
        showToast("Ошибка получения результатов расшифровки", "error");
      }
    }
  });

  sseEventSource.addEventListener("error", () => {
    if (sseEventSource) {
      sseEventSource.close();
      sseEventSource = null;
      currentConnectedJobId = null;
    }
    if (globalStore.state.status === "LOADING") {
      showToast("Потеряно соединение с сервером обновлений.", "error");
    }
  });
}
