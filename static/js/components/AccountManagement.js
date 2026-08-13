// filename: static/js/components/AccountManagement.js
/**
 * Account Management & Transcription History Web Component (<account-management>)
 * Features:
 * - Full light/dark theme compatibility using CSS design tokens
 * - User Profile view & update (first name, last name, email)
 * - Security credential updates (password verification & change)
 * - Transcription history dashboard with search, sorting, and pagination
 * - Detail modal/drawer with audio playback, metadata preview, and full text copying
 * - Optimistic deletion confirmation modal with Escape key accessibility
 */

import { globalStore, showToast } from "../store.js";
import { router } from "../router.js";

export class AccountManagement extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.activeTab = "history"; // "history" | "profile"
    this.profileData = null;
    this.transcriptions = [];
    this.pagination = { page: 1, limit: 10, total: 0, total_pages: 1 };
    this.searchQuery = "";
    this.sortBy = "-created_at";
    this.selectedTranscription = null;
    this.deleteCandidate = null;
    this.isLoading = false;
    this.onKeyDown = this.handleKeyDown.bind(this);
  }

  connectedCallback() {
    this.render();
    this.loadProfile();
    window.addEventListener("keydown", this.onKeyDown);
  }

  disconnectedCallback() {
    window.removeEventListener("keydown", this.onKeyDown);
  }

  handleKeyDown(e) {
    if (e.key === "Escape") {
      this.closeDetailModal();
      this.closeDeleteModal();
    }
  }

  async loadProfile() {
    try {
      const res = await fetch("/api/v1/account/me");
      if (res.ok) {
        this.profileData = await res.json();
        this.updateProfileForm();
      } else if (res.status === 401) {
        window.location.href = "/accounts/login/";
      }
    } catch (err) {
      console.error("[AccountManagement] Error fetching profile:", err);
    }
  }

  /**
   * Synchronizes component view, active tabs, and filter parameters from the Router.
   * @param {"history" | "profile" | "security"} [subTab]
   * @param {Object} [queryParams]
   */
  syncFromRoute(subTab = "history", queryParams = {}) {
    const targetTab = subTab === "profile" || subTab === "security" ? "profile" : "history";
    this.activeTab = targetTab;

    if (!this.shadowRoot || !this.shadowRoot.getElementById("tabHistoryBtn")) {
      this.render();
    } else {
      this.switchTab(targetTab, false);
    }

    if (queryParams.page) {
      this.pagination.page = Math.max(1, parseInt(queryParams.page, 10) || 1);
    }
    if (queryParams.search !== undefined) {
      this.searchQuery = queryParams.search || "";
      const searchInput = this.shadowRoot?.getElementById("historySearchInput");
      if (searchInput) searchInput.value = this.searchQuery;
    }
    if (queryParams.sort_by) {
      this.sortBy = queryParams.sort_by;
      const sortSelect = this.shadowRoot?.getElementById("historySortSelect");
      if (sortSelect) sortSelect.value = this.sortBy;
    }

    this.loadTranscriptions();

    if (queryParams.detail) {
      this.openDetailModal(queryParams.detail, false);
    }
  }

  switchTab(tabName, updateUrl = true) {
    this.activeTab = tabName;
    const historyTabBtn = this.shadowRoot?.getElementById("tabHistoryBtn");
    const profileTabBtn = this.shadowRoot?.getElementById("tabProfileBtn");
    const historyContent = this.shadowRoot?.getElementById("historyTabContent");
    const profileContent = this.shadowRoot?.getElementById("profileTabContent");

    if (!historyTabBtn || !profileTabBtn || !historyContent || !profileContent) return;

    if (tabName === "profile") {
      profileTabBtn.classList.add("active");
      profileTabBtn.setAttribute("aria-selected", "true");
      historyTabBtn.classList.remove("active");
      historyTabBtn.setAttribute("aria-selected", "false");
      profileContent.classList.add("active");
      historyContent.classList.remove("active");
      if (updateUrl) {
        router.navigate("/account/profile", { replace: false });
      }
    } else {
      historyTabBtn.classList.add("active");
      historyTabBtn.setAttribute("aria-selected", "true");
      profileTabBtn.classList.remove("active");
      profileTabBtn.setAttribute("aria-selected", "false");
      historyContent.classList.add("active");
      profileContent.classList.remove("active");
      if (updateUrl) {
        router.navigate("/account/history", { replace: false });
      }
    }
  }

  async loadTranscriptions() {
    this.isLoading = true;
    this.renderHistoryTable();
    try {
      const query = new URLSearchParams({
        page: this.pagination.page.toString(),
        limit: this.pagination.limit.toString(),
        sort_by: this.sortBy,
      });
      if (this.searchQuery) {
        query.append("search", this.searchQuery);
      }

      const res = await fetch(`/api/v1/account/transcriptions?${query.toString()}`);
      if (res.ok) {
        const data = await res.json();
        this.transcriptions = data.items;
        this.pagination = {
          page: data.page,
          limit: data.limit,
          total: data.total,
          total_pages: data.total_pages,
        };
      } else if (res.status === 401) {
        window.location.href = "/accounts/login/";
      } else {
        showToast("Ошибка при загрузке истории транскрипций", "error");
      }
    } catch (err) {
      console.error("[AccountManagement] Error loading transcriptions:", err);
      showToast("Ошибка сети при получении истории", "error");
    } finally {
      this.isLoading = false;
      this.renderHistoryTable();
    }
  }

  formatDuration(seconds) {
    if (!seconds || isNaN(seconds)) return "00:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }

  formatDate(isoString) {
    if (!isoString) return "—";
    const date = new Date(isoString);
    return date.toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  getStatusBadge(status) {
    const s = (status || "").toLowerCase();
    switch (s) {
      case "completed":
        return `<span class="badge badge-success"><span class="badge-dot"></span>Готово</span>`;
      case "processing":
        return `<span class="badge badge-warning"><span class="badge-dot pulse"></span>Обработка</span>`;
      case "pending":
        return `<span class="badge badge-info"><span class="badge-dot"></span>В очереди</span>`;
      case "failed":
        return `<span class="badge badge-danger"><span class="badge-dot"></span>Ошибка</span>`;
      default:
        return `<span class="badge badge-neutral">${status || "Неизвестно"}</span>`;
    }
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          width: 100%;
          font-family: var(--font-sans, system-ui, -apple-system, sans-serif);
          color: var(--text-primary, #f8fafc);
          box-sizing: border-box;
        }

        .account-card {
          background: var(--bg-glass-card, rgba(15, 23, 42, 0.8));
          border: 1px solid var(--border-color-card, rgba(255, 255, 255, 0.12));
          border-radius: var(--radius-xl, 24px);
          padding: 28px;
          backdrop-filter: var(--backdrop-blur, blur(16px));
          -webkit-backdrop-filter: var(--backdrop-blur, blur(16px));
          box-shadow: var(--shadow-lg, 0 20px 40px rgba(0,0,0,0.4));
          transition: border-color var(--transition-normal, 0.25s ease);
        }

        .nav-tabs {
          display: flex;
          gap: 12px;
          border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.1));
          padding-bottom: 16px;
          margin-bottom: 24px;
          flex-wrap: wrap;
        }

        .tab-btn {
          background: transparent;
          border: 1px solid transparent;
          color: var(--text-secondary, #94a3b8);
          font-family: var(--font-sans);
          font-weight: 600;
          font-size: 0.925rem;
          padding: 10px 18px;
          border-radius: var(--radius-md, 12px);
          cursor: pointer;
          transition: all var(--transition-fast, 0.15s ease);
          display: inline-flex;
          align-items: center;
          gap: 8px;
          user-select: none;
        }

        .tab-btn:hover {
          color: var(--text-primary, #ffffff);
          background: var(--bg-surface-hover, rgba(255,255,255,0.06));
          border-color: var(--border-color);
        }

        .tab-btn.active {
          color: #ffffff;
          background: var(--primary-gradient, linear-gradient(135deg, #6366f1, #8b5cf6));
          box-shadow: var(--shadow-glow, 0 0 15px rgba(99,102,241,0.35));
          border-color: transparent;
        }

        .tab-content {
          display: none;
        }

        .tab-content.active {
          display: block;
        }

        /* Controls bar */
        .controls-bar {
          display: flex;
          flex-wrap: wrap;
          gap: 12px;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
        }

        .search-box {
          position: relative;
          flex: 1;
          min-width: 240px;
        }

        .search-input {
          width: 100%;
          background: var(--bg-surface-elevated, #1e293b);
          border: 1px solid var(--border-color, rgba(255,255,255,0.12));
          border-radius: var(--radius-md, 12px);
          padding: 10px 16px 10px 42px;
          color: var(--text-primary, #ffffff);
          font-size: 0.9rem;
          font-family: var(--font-sans);
          outline: none;
          box-sizing: border-box;
          transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }

        .search-input:focus {
          border-color: var(--primary, #6366f1);
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
        }

        .search-icon {
          position: absolute;
          left: 14px;
          top: 50%;
          transform: translateY(-50%);
          color: var(--text-muted, #64748b);
          pointer-events: none;
        }

        .filter-controls {
          display: flex;
          gap: 10px;
          align-items: center;
        }

        .select-input {
          background: var(--bg-surface-elevated, #1e293b);
          border: 1px solid var(--border-color, rgba(255,255,255,0.12));
          border-radius: var(--radius-md, 12px);
          padding: 10px 14px;
          color: var(--text-primary, #ffffff);
          font-size: 0.875rem;
          font-family: var(--font-sans);
          outline: none;
          cursor: pointer;
        }

        /* Table styles */
        .table-responsive {
          width: 100%;
          overflow-x: auto;
          border-radius: var(--radius-md, 12px);
          border: 1px solid var(--border-color, rgba(255,255,255,0.1));
        }

        .data-table {
          width: 100%;
          border-collapse: collapse;
          text-align: left;
          font-size: 0.875rem;
        }

        .data-table th {
          background: var(--bg-surface-elevated, rgba(15, 23, 42, 0.8));
          color: var(--text-secondary, #94a3b8);
          padding: 14px 18px;
          font-weight: 700;
          text-transform: uppercase;
          font-size: 0.75rem;
          letter-spacing: 0.05em;
          border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.1));
        }

        .data-table td {
          padding: 14px 18px;
          border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.06));
          color: var(--text-primary, #f8fafc);
        }

        .data-table tbody tr {
          transition: background 0.15s ease;
        }

        .data-table tbody tr:hover {
          background: var(--bg-surface-hover, rgba(255, 255, 255, 0.05));
        }

        .title-cell {
          font-weight: 600;
          color: var(--text-primary, #ffffff);
          display: flex;
          flex-direction: column;
        }

        .subtitle-cell {
          font-size: 0.78rem;
          color: var(--text-muted, #64748b);
          margin-top: 2px;
          font-family: var(--font-mono, monospace);
        }

        /* Badges */
        .badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 4px 10px;
          border-radius: 9999px;
          font-size: 0.75rem;
          font-weight: 700;
        }

        .badge-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: currentColor;
        }

        .badge-dot.pulse {
          animation: pulseAnim 1.5s infinite;
        }

        @keyframes pulseAnim {
          0% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(1.3); }
          100% { opacity: 1; transform: scale(1); }
        }

        .badge-success { background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.35); }
        .badge-warning { background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.35); }
        .badge-info { background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.35); }
        .badge-danger { background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.35); }
        .badge-neutral { background: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid var(--border-color, rgba(148, 163, 184, 0.3)); }

        /* Buttons */
        .btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          padding: 8px 14px;
          border-radius: var(--radius-sm, 8px);
          font-family: var(--font-sans);
          font-size: 0.85rem;
          font-weight: 600;
          border: none;
          cursor: pointer;
          transition: all 0.15s ease;
          user-select: none;
        }

        .btn-primary {
          background: var(--primary-gradient, linear-gradient(135deg, #6366f1, #8b5cf6));
          color: #ffffff;
          box-shadow: 0 2px 10px rgba(99, 102, 241, 0.25);
        }

        .btn-primary:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
        }

        .btn-secondary {
          background: var(--bg-surface-elevated, #1e293b);
          color: var(--text-primary, #ffffff);
          border: 1px solid var(--border-color, rgba(255,255,255,0.12));
        }

        .btn-secondary:hover {
          background: var(--bg-surface-hover, rgba(255,255,255,0.08));
          border-color: var(--border-color-hover);
        }

        .btn-danger {
          background: rgba(239, 68, 68, 0.15);
          color: #ef4444;
          border: 1px solid rgba(239, 68, 68, 0.35);
        }

        .btn-danger:hover {
          background: rgba(239, 68, 68, 0.25);
          color: #fca5a5;
        }

        .btn-sm {
          padding: 6px 10px;
          font-size: 0.8rem;
        }

        .actions-cell {
          display: flex;
          gap: 8px;
        }

        /* Pagination */
        .pagination-wrapper {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-top: 20px;
          font-size: 0.85rem;
          color: var(--text-secondary, #94a3b8);
          flex-wrap: wrap;
          gap: 12px;
        }

        .pagination-btns {
          display: flex;
          gap: 6px;
        }

        /* Forms in Profile Tab */
        .form-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: 24px;
        }

        .form-section {
          background: var(--bg-surface-elevated, #1e293b);
          border: 1px solid var(--border-color, rgba(255,255,255,0.1));
          border-radius: var(--radius-lg, 18px);
          padding: 24px;
        }

        .form-section-title {
          font-size: 1.05rem;
          font-weight: 700;
          color: var(--text-primary, #ffffff);
          margin-bottom: 20px;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .form-group {
          margin-bottom: 16px;
        }

        .form-label {
          display: block;
          font-size: 0.825rem;
          font-weight: 600;
          color: var(--text-secondary, #94a3b8);
          margin-bottom: 6px;
        }

        .form-input {
          width: 100%;
          background: var(--bg-surface, #0f172a);
          border: 1px solid var(--border-color, rgba(255,255,255,0.12));
          border-radius: var(--radius-md, 12px);
          padding: 11px 14px;
          color: var(--text-primary, #ffffff);
          font-size: 0.9rem;
          font-family: var(--font-sans);
          outline: none;
          box-sizing: border-box;
          transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }

        .form-input:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .form-input:focus:not(:disabled) {
          border-color: var(--primary, #6366f1);
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
        }

        /* Modals */
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.75);
          backdrop-filter: blur(8px);
          -webkit-backdrop-filter: blur(8px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          opacity: 0;
          pointer-events: none;
          transition: opacity 0.25s ease;
        }

        .modal-overlay.open {
          opacity: 1;
          pointer-events: auto;
        }

        .modal-box {
          background: var(--bg-surface-elevated, #1e293b);
          border: 1px solid var(--border-color-card, rgba(255,255,255,0.15));
          border-radius: var(--radius-xl, 24px);
          width: 90%;
          max-width: 680px;
          max-height: 85vh;
          overflow-y: auto;
          padding: 28px;
          box-shadow: var(--shadow-lg);
          transform: translateY(20px);
          transition: transform 0.25s ease;
        }

        .modal-overlay.open .modal-box {
          transform: translateY(0);
        }

        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.1));
          padding-bottom: 16px;
          margin-bottom: 20px;
        }

        .modal-title {
          font-size: 1.15rem;
          font-weight: 800;
          color: var(--text-primary, #ffffff);
        }

        .modal-close-btn {
          background: transparent;
          border: none;
          color: var(--text-secondary, #94a3b8);
          font-size: 1.5rem;
          cursor: pointer;
          line-height: 1;
          padding: 4px;
          transition: color 0.15s ease;
        }

        .modal-close-btn:hover {
          color: var(--text-primary, #ffffff);
        }

        .modal-body {
          margin-bottom: 24px;
        }

        .audio-player-container {
          background: var(--bg-surface, #0f172a);
          border: 1px solid var(--border-color);
          border-radius: var(--radius-md, 12px);
          padding: 16px;
          margin-bottom: 20px;
        }

        audio {
          width: 100%;
          border-radius: 8px;
          outline: none;
        }

        .transcript-text-box {
          background: var(--bg-surface, #0f172a);
          border: 1px solid var(--border-color, rgba(255,255,255,0.08));
          border-radius: var(--radius-md, 12px);
          padding: 16px;
          max-height: 280px;
          overflow-y: auto;
          white-space: pre-wrap;
          font-size: 0.9rem;
          line-height: 1.6;
          color: var(--text-primary, #f8fafc);
        }

        .modal-footer {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
        }
      </style>

      <div class="account-card">
        <!-- Navigation Tabs -->
        <div class="nav-tabs" role="tablist">
          <button class="tab-btn ${this.activeTab === "history" ? "active" : ""}" id="tabHistoryBtn" role="tab" aria-selected="${this.activeTab === "history"}">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            История транскрипций
          </button>

          <button class="tab-btn ${this.activeTab === "profile" ? "active" : ""}" id="tabProfileBtn" role="tab" aria-selected="${this.activeTab === "profile"}">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
              <circle cx="12" cy="7" r="4"></circle>
            </svg>
            Профиль и безопасность
          </button>
        </div>

        <!-- History Tab Content -->
        <div class="tab-content ${this.activeTab === "history" ? "active" : ""}" id="historyTabContent" role="tabpanel">
          <div class="controls-bar">
            <div class="search-box">
              <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
              <input type="text" class="search-input" id="historySearchInput" placeholder="Поиск по названию транскрипции..." />
            </div>

            <div class="filter-controls">
              <select class="select-input" id="historySortSelect">
                <option value="-created_at">Сначала новые</option>
                <option value="created_at">Сначала старые</option>
                <option value="title">По названию (А-Я)</option>
                <option value="-duration_seconds">По длительности</option>
              </select>

              <button class="btn btn-secondary" id="refreshHistoryBtn" title="Обновить список">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="23 4 23 10 17 10"></polyline>
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                </svg>
              </button>
            </div>
          </div>

          <!-- Table Container -->
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Название и файл</th>
                  <th>Дата создания</th>
                  <th>Длительность</th>
                  <th>Статус</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody id="historyTableBody">
                <tr>
                  <td colspan="5" style="text-align:center; padding: 30px; color: var(--text-muted);">
                    Загрузка истории транскрипций...
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination Bar -->
          <div class="pagination-wrapper">
            <span id="paginationInfo">Показано 0 из 0</span>
            <div class="pagination-btns">
              <button class="btn btn-secondary btn-sm" id="prevPageBtn" disabled>&larr; Назад</button>
              <button class="btn btn-secondary btn-sm" id="nextPageBtn" disabled>Вперед &rarr;</button>
            </div>
          </div>
        </div>

        <!-- Profile Tab Content -->
        <div class="tab-content ${this.activeTab === "profile" ? "active" : ""}" id="profileTabContent" role="tabpanel">
          <div class="form-grid">
            <!-- Personal Info Form -->
            <div class="form-section">
              <div class="form-section-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                  <circle cx="12" cy="7" r="4"></circle>
                </svg>
                Личные данные
              </div>

              <form id="profileInfoForm">
                <div class="form-group">
                  <label class="form-label">Имя пользователя (Логин)</label>
                  <input type="text" class="form-input" id="usernameInput" disabled />
                </div>

                <div class="form-group">
                  <label class="form-label">Имя</label>
                  <input type="text" class="form-input" id="firstNameInput" placeholder="Иван" />
                </div>

                <div class="form-group">
                  <label class="form-label">Фамилия</label>
                  <input type="text" class="form-input" id="lastNameInput" placeholder="Иванов" />
                </div>

                <div class="form-group">
                  <label class="form-label">Электронная почта</label>
                  <input type="email" class="form-input" id="emailInput" placeholder="user@example.com" />
                </div>

                <button type="submit" class="btn btn-primary" id="saveProfileBtn">
                  Сохранить изменения
                </button>
              </form>
            </div>

            <!-- Password Change Form -->
            <div class="form-section">
              <div class="form-section-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                </svg>
                Безопасность и пароль
              </div>

              <form id="passwordChangeForm">
                <div class="form-group">
                  <label class="form-label">Текущий пароль</label>
                  <input type="password" class="form-input" id="currentPasswordInput" required placeholder="••••••••" />
                </div>

                <div class="form-group">
                  <label class="form-label">Новый пароль (мин. 8 символов)</label>
                  <input type="password" class="form-input" id="newPasswordInput" required minlength="8" placeholder="••••••••" />
                </div>

                <button type="submit" class="btn btn-primary" id="savePasswordBtn">
                  Обновить пароль
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>

      <!-- Detail Modal Drawer -->
      <div class="modal-overlay" id="detailModalOverlay" role="dialog" aria-modal="true" aria-labelledby="detailModalTitle">
        <div class="modal-box">
          <div class="modal-header">
            <div class="modal-title" id="detailModalTitle">Детали стенограммы</div>
            <button class="modal-close-btn" id="closeDetailModalBtn" aria-label="Закрыть модальное окно">&times;</button>
          </div>
          <div class="modal-body">
            <div class="audio-player-container">
              <p style="font-size:0.82rem; color:var(--text-secondary); margin-bottom:8px;">Аудиозапись:</p>
              <audio id="detailAudioPlayer" controls></audio>
            </div>
            <div style="margin-bottom: 12px; font-size: 0.85rem; color: var(--text-secondary);" id="detailModalMeta"></div>
            <p style="font-size:0.85rem; font-weight:600; margin-bottom:6px; color:var(--text-primary);">Текст расшифровки:</p>
            <div class="transcript-text-box" id="detailModalText"></div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" id="copyTextBtn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
              Копировать текст
            </button>
            <button class="btn btn-primary" id="openInStudioModalBtn" style="background:var(--primary); border-color:var(--primary);">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
              </svg>
              Открыть в Студии
            </button>
            <button class="btn btn-secondary" id="closeDetailModalFooterBtn">Закрыть</button>
          </div>
        </div>
      </div>

      <!-- Delete Confirmation Modal -->
      <div class="modal-overlay" id="deleteModalOverlay" role="dialog" aria-modal="true" aria-labelledby="deleteModalHeading">
        <div class="modal-box" style="max-width:480px;">
          <div class="modal-header">
            <div class="modal-title" id="deleteModalHeading" style="color:var(--accent-danger, #ef4444);">Подтверждение удаления</div>
            <button class="modal-close-btn" id="closeDeleteModalBtn" aria-label="Закрыть">&times;</button>
          </div>
          <div class="modal-body">
            <p style="font-size:0.95rem; line-height:1.5; color:var(--text-primary);" id="deleteModalMessage">
              Вы уверены, что хотите безвозвратно удалить запись транскрипции?
            </p>
          </div>
          <div class="modal-footer">
            <button class="btn btn-secondary" id="cancelDeleteBtn">Отмена</button>
            <button class="btn btn-danger" id="confirmDeleteBtn">Удалить безвозвратно</button>
          </div>
        </div>
      </div>
    `;

    this.bindEvents();
  }

  updateProfileForm() {
    if (!this.profileData) return;
    const usernameInput = this.shadowRoot.getElementById("usernameInput");
    const firstNameInput = this.shadowRoot.getElementById("firstNameInput");
    const lastNameInput = this.shadowRoot.getElementById("lastNameInput");
    const emailInput = this.shadowRoot.getElementById("emailInput");

    if (usernameInput) usernameInput.value = this.profileData.username || "";
    if (firstNameInput) firstNameInput.value = this.profileData.first_name || "";
    if (lastNameInput) lastNameInput.value = this.profileData.last_name || "";
    if (emailInput) emailInput.value = this.profileData.email || "";
  }

  renderHistoryTable() {
    const tbody = this.shadowRoot.getElementById("historyTableBody");
    const info = this.shadowRoot.getElementById("paginationInfo");
    const prevBtn = this.shadowRoot.getElementById("prevPageBtn");
    const nextBtn = this.shadowRoot.getElementById("nextPageBtn");

    if (!tbody) return;

    if (this.isLoading) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align:center; padding: 30px; color: var(--text-muted);">
            Загрузка записей...
          </td>
        </tr>
      `;
      return;
    }

    if (this.transcriptions.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align:center; padding: 30px; color: var(--text-muted);">
            Транскрипции не найдены.
          </td>
        </tr>
      `;
      if (info) info.textContent = "Показано 0 из 0";
      if (prevBtn) prevBtn.disabled = true;
      if (nextBtn) nextBtn.disabled = true;
      return;
    }

    tbody.innerHTML = this.transcriptions
      .map(
        (item) => `
        <tr>
          <td>
            <div class="title-cell">
              <span>${item.title || "Запись"}</span>
              <span class="subtitle-cell">${item.original_filename || "—"}</span>
            </div>
          </td>
          <td>${this.formatDate(item.created_at)}</td>
          <td>${this.formatDuration(item.duration_seconds)}</td>
          <td>${this.getStatusBadge(item.status)}</td>
          <td>
            <div class="actions-cell">
              <button class="btn btn-primary btn-sm studio-btn" data-id="${item.id}" title="Открыть в интерактивной студии">
                Студия
              </button>
              <button class="btn btn-secondary btn-sm view-btn" data-id="${item.id}" title="Просмотреть детали">
                Детали
              </button>
              <button class="btn btn-danger btn-sm delete-btn" data-id="${item.id}" title="Удалить запись">
                Удалить
              </button>
            </div>
          </td>
        </tr>
      `
      )
      .join("");

    const startItem = (this.pagination.page - 1) * this.pagination.limit + 1;
    const endItem = Math.min(
      this.pagination.page * this.pagination.limit,
      this.pagination.total
    );
    if (info) {
      info.textContent = `Показано ${startItem}-${endItem} из ${this.pagination.total} записей (Стр. ${this.pagination.page} из ${this.pagination.total_pages})`;
    }

    if (prevBtn) prevBtn.disabled = this.pagination.page <= 1;
    if (nextBtn) nextBtn.disabled = this.pagination.page >= this.pagination.total_pages;

    // Attach row button listeners
    tbody.querySelectorAll(".studio-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        router.navigate(`/jobs/${id}`);
      });
    });

    tbody.querySelectorAll(".view-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        this.openDetailModal(id, true);
      });
    });

    tbody.querySelectorAll(".delete-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        this.openDeleteModal(id);
      });
    });
  }

  async openDetailModal(id, updateUrl = true) {
    try {
      const res = await fetch(`/api/v1/account/transcriptions/${id}`);
      if (!res.ok) {
        showToast("Не удалось загрузить детали транскрипции", "error");
        return;
      }

      const data = await res.json();
      this.selectedTranscription = data;

      const modalOverlay = this.shadowRoot.getElementById("detailModalOverlay");
      const titleEl = this.shadowRoot.getElementById("detailModalTitle");
      const metaEl = this.shadowRoot.getElementById("detailModalMeta");
      const textEl = this.shadowRoot.getElementById("detailModalText");
      const player = this.shadowRoot.getElementById("detailAudioPlayer");

      if (titleEl) titleEl.textContent = data.title;
      if (metaEl) {
        metaEl.innerHTML = `
          <strong>Файл:</strong> ${data.original_filename || "—"} |
          <strong>Дата:</strong> ${this.formatDate(data.created_at)} |
          <strong>Длительность:</strong> ${this.formatDuration(data.duration_seconds)} |
          <strong>Язык:</strong> ${(data.language || "ru").toUpperCase()}
        `;
      }
      if (textEl) {
        textEl.textContent =
          data.transcription_text || "Текст стенограммы отсутствует или находится в обработке.";
      }
      if (player) {
        player.src = data.audio_url || `/api/v1/account/transcriptions/${data.id}/audio`;
      }

      if (modalOverlay) modalOverlay.classList.add("open");

      if (updateUrl) {
        router.updateQueryParams({ detail: id }, { replace: false });
      }
    } catch (err) {
      console.error("[AccountManagement] Error opening detail modal:", err);
    }
  }

  closeDetailModal(updateUrl = true) {
    const modalOverlay = this.shadowRoot.getElementById("detailModalOverlay");
    const player = this.shadowRoot.getElementById("detailAudioPlayer");
    if (player) {
      player.pause();
      player.src = "";
    }
    if (modalOverlay) modalOverlay.classList.remove("open");

    if (updateUrl) {
      router.updateQueryParams({ detail: null }, { replace: true });
    }
  }

  openDeleteModal(id) {
    const item = this.transcriptions.find((t) => t.id === id);
    if (!item) return;

    this.deleteCandidate = item;
    const msg = this.shadowRoot.getElementById("deleteModalMessage");
    if (msg) {
      msg.textContent = `Вы действительно хотите безвозвратно удалить запись "${item.title}" и связанный аудиофайл?`;
    }

    const modalOverlay = this.shadowRoot.getElementById("deleteModalOverlay");
    if (modalOverlay) modalOverlay.classList.add("open");
  }

  closeDeleteModal() {
    this.deleteCandidate = null;
    const modalOverlay = this.shadowRoot.getElementById("deleteModalOverlay");
    if (modalOverlay) modalOverlay.classList.remove("open");
  }

  async executeDelete() {
    if (!this.deleteCandidate) return;
    const id = this.deleteCandidate.id;
    this.closeDeleteModal();

    try {
      const res = await fetch(`/api/v1/account/transcriptions/${id}`, {
        method: "DELETE",
      });

      if (res.status === 204 || res.ok) {
        showToast("Запись транскрипции успешно удалена", "success");
        this.transcriptions = this.transcriptions.filter((t) => t.id !== id);
        this.loadTranscriptions();
      } else {
        showToast("Ошибка при удалении транскрипции", "error");
      }
    } catch (err) {
      console.error("[AccountManagement] Delete execution error:", err);
      showToast("Ошибка сети при удалении записи", "error");
    }
  }

  bindEvents() {
    // Tab Switching
    const historyTabBtn = this.shadowRoot.getElementById("tabHistoryBtn");
    const profileTabBtn = this.shadowRoot.getElementById("tabProfileBtn");

    if (historyTabBtn && profileTabBtn) {
      historyTabBtn.addEventListener("click", () => this.switchTab("history", true));
      profileTabBtn.addEventListener("click", () => this.switchTab("profile", true));
    }

    // Search and Sort
    const searchInput = this.shadowRoot.getElementById("historySearchInput");
    if (searchInput) {
      let timeout = null;
      searchInput.addEventListener("input", (e) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
          this.searchQuery = e.target.value;
          this.pagination.page = 1;
          router.updateQueryParams(
            { page: 1, search: this.searchQuery || null },
            { replace: true }
          );
          this.loadTranscriptions();
        }, 350);
      });
    }

    const sortSelect = this.shadowRoot.getElementById("historySortSelect");
    if (sortSelect) {
      sortSelect.addEventListener("change", (e) => {
        this.sortBy = e.target.value;
        this.pagination.page = 1;
        router.updateQueryParams(
          { page: 1, sort_by: this.sortBy },
          { replace: true }
        );
        this.loadTranscriptions();
      });
    }

    const refreshBtn = this.shadowRoot.getElementById("refreshHistoryBtn");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => this.loadTranscriptions());
    }

    // Pagination
    const prevBtn = this.shadowRoot.getElementById("prevPageBtn");
    const nextBtn = this.shadowRoot.getElementById("nextPageBtn");

    if (prevBtn) {
      prevBtn.addEventListener("click", () => {
        if (this.pagination.page > 1) {
          this.pagination.page--;
          router.updateQueryParams({ page: this.pagination.page }, { replace: true });
          this.loadTranscriptions();
        }
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener("click", () => {
        if (this.pagination.page < this.pagination.total_pages) {
          this.pagination.page++;
          router.updateQueryParams({ page: this.pagination.page }, { replace: true });
          this.loadTranscriptions();
        }
      });
    }

    // Detail Modal actions
    const closeDetailBtn = this.shadowRoot.getElementById("closeDetailModalBtn");
    const closeDetailFooterBtn = this.shadowRoot.getElementById("closeDetailModalFooterBtn");
    if (closeDetailBtn) closeDetailBtn.addEventListener("click", () => this.closeDetailModal());
    if (closeDetailFooterBtn) closeDetailFooterBtn.addEventListener("click", () => this.closeDetailModal());

    const copyBtn = this.shadowRoot.getElementById("copyTextBtn");
    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        if (this.selectedTranscription && this.selectedTranscription.transcription_text) {
          navigator.clipboard.writeText(this.selectedTranscription.transcription_text);
          showToast("Текст расшифровки скопирован в буфер обмена!", "success");
        }
      });
    }

    const openInStudioBtn = this.shadowRoot.getElementById("openInStudioModalBtn");
    if (openInStudioBtn) {
      openInStudioBtn.addEventListener("click", () => {
        if (this.selectedTranscription && this.selectedTranscription.id) {
          const id = this.selectedTranscription.id;
          this.closeDetailModal(true);
          router.navigate(`/jobs/${id}`);
        }
      });
    }

    // Delete Modal actions
    const closeDeleteBtn = this.shadowRoot.getElementById("closeDeleteModalBtn");
    const cancelDeleteBtn = this.shadowRoot.getElementById("cancelDeleteBtn");
    const confirmDeleteBtn = this.shadowRoot.getElementById("confirmDeleteBtn");

    if (closeDeleteBtn) closeDeleteBtn.addEventListener("click", () => this.closeDeleteModal());
    if (cancelDeleteBtn) cancelDeleteBtn.addEventListener("click", () => this.closeDeleteModal());
    if (confirmDeleteBtn) confirmDeleteBtn.addEventListener("click", () => this.executeDelete());

    // Profile form submission
    const profileForm = this.shadowRoot.getElementById("profileInfoForm");
    if (profileForm) {
      profileForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const firstName = this.shadowRoot.getElementById("firstNameInput").value;
        const lastName = this.shadowRoot.getElementById("lastNameInput").value;
        const email = this.shadowRoot.getElementById("emailInput").value;

        try {
          const res = await fetch("/api/v1/account/me", {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              first_name: firstName,
              last_name: lastName,
              email: email,
            }),
          });

          if (res.ok) {
            this.profileData = await res.json();
            showToast("Данные профиля успешно обновлены!", "success");
            const nameEl = document.getElementById("userDisplayName");
            if (nameEl)
              nameEl.textContent = this.profileData.full_name || this.profileData.username;
          } else {
            showToast("Ошибка при сохранении данных профиля", "error");
          }
        } catch (err) {
          showToast("Ошибка сети при обновлении профиля", "error");
        }
      });
    }

    // Password form submission
    const passwordForm = this.shadowRoot.getElementById("passwordChangeForm");
    if (passwordForm) {
      passwordForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const currentPassword = this.shadowRoot.getElementById("currentPasswordInput").value;
        const newPassword = this.shadowRoot.getElementById("newPasswordInput").value;

        try {
          const res = await fetch("/api/v1/account/me", {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              current_password: currentPassword,
              new_password: newPassword,
            }),
          });

          if (res.ok) {
            showToast("Пароль успешно изменен!", "success");
            passwordForm.reset();
          } else {
            const errData = await res.json();
            showToast(errData.detail || "Не удалось обновить пароль", "error");
          }
        } catch (err) {
          showToast("Ошибка сети при изменении пароля", "error");
        }
      });
    }
  }
}

customElements.define("account-management", AccountManagement);
