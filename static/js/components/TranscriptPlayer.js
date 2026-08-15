// filename: static/js/components/TranscriptPlayer.js
/**
 * Interactive Audio & Transcript Player Web Component:
 * - High-performance non-destructive audio playback with O(1) active word time highlighting
 * - Ctrl+F style in-transcript search with match highlighting, counter, and keyboard navigation
 * - Adaptive light/dark theme styling with high contrast design tokens
 * - Speaker color badges & global renaming
 * - Multi-format export actions (TXT, PDF, DOCX, SRT, VTT, JSON)
 */
import { globalStore, showToast } from "../store.js";
import { router } from "../router.js";

export class TranscriptPlayer extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.unsubscribe = null;
    this.searchQuery = "";
    this.searchResults = [];
    this.currentMatchIndex = -1;
    this.currentJobId = null;
    this.currentStatus = null;
    this.currentTranscript = null;
    this.activeWordSpans = new Set();
    this.targetOldSpeaker = null;
    this.isRenaming = false;
  }

  connectedCallback() {
    this.unsubscribe = globalStore.subscribe((state, changedKey) => {
      if (changedKey === "currentTime") {
        this.updateActiveWords(state.currentTime);
      } else if (state.status === "LOADING" && (changedKey === "progress" || changedKey === "stepMessage")) {
        this.updateLoadingProgress(state.progress, state.stepMessage);
      } else {
        this.handleStateUpdate(state);
      }
    });

    if (globalStore.state.initialSearchQuery) {
      this.searchQuery = globalStore.state.initialSearchQuery;
    }

    this.render(globalStore.state);
  }

  updateLoadingProgress(progress, stepMessage) {
    const fill = this.shadowRoot.querySelector("#loadingProgressBarFill");
    const text = this.shadowRoot.querySelector("#loadingProgressPercent");
    const step = this.shadowRoot.querySelector("#loadingStepMessage");

    const clampedPercent = Math.min(Math.max(progress || 0, 0), 100);

    if (fill) {
      fill.style.width = `${clampedPercent}%`;
    }
    if (text) {
      text.textContent = `${Math.round(clampedPercent)}%`;
    }
    if (step && stepMessage) {
      step.textContent = stepMessage;
    }
  }

  disconnectedCallback() {
    if (this.unsubscribe) this.unsubscribe();
  }

  getSpeakerColor(speakerName) {
    const palette = [
      {
        bg: "rgba(99, 102, 241, 0.16)",
        text: "var(--primary, #6366f1)",
        border: "rgba(99, 102, 241, 0.35)",
      },
      {
        bg: "rgba(16, 185, 129, 0.16)",
        text: "var(--accent-success, #10b981)",
        border: "rgba(16, 185, 129, 0.35)",
      },
      {
        bg: "rgba(245, 158, 11, 0.16)",
        text: "var(--accent-warning, #f59e0b)",
        border: "rgba(245, 158, 11, 0.35)",
      },
      {
        bg: "rgba(236, 72, 153, 0.16)",
        text: "#ec4899",
        border: "rgba(236, 72, 153, 0.35)",
      },
      {
        bg: "rgba(6, 182, 212, 0.16)",
        text: "var(--accent-info, #06b6d4)",
        border: "rgba(6, 182, 212, 0.35)",
      },
    ];
    let hash = 0;
    const name = speakerName || "Speaker";
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    const index = Math.abs(hash) % palette.length;
    return palette[index];
  }

  getUniqueSpeakers(utterances) {
    if (!utterances || !Array.isArray(utterances)) return [];
    const seen = new Set();
    const result = [];
    utterances.forEach((u) => {
      const spk = u.speaker || "Спикер";
      if (!seen.has(spk)) {
        seen.add(spk);
        result.push(spk);
      }
    });
    return result;
  }

  openSpeakerRenameModal(speakerName) {
    this.targetOldSpeaker = speakerName;
    const modal = this.shadowRoot.getElementById("speakerRenameModalOverlay");
    const oldNameEl = this.shadowRoot.getElementById("modalOldSpeakerName");
    const inputEl = this.shadowRoot.getElementById("newSpeakerNameInput");

    if (oldNameEl) oldNameEl.textContent = `«${speakerName}»`;
    if (inputEl) {
      inputEl.value = speakerName;
      setTimeout(() => {
        inputEl.focus();
        inputEl.select();
      }, 50);
    }
    if (modal) {
      modal.classList.add("open");
    }
  }

  closeSpeakerRenameModal() {
    this.targetOldSpeaker = null;
    const modal = this.shadowRoot.getElementById("speakerRenameModalOverlay");
    if (modal) {
      modal.classList.remove("open");
    }
  }

  async executeSpeakerRename(newName) {
    const cleanNewName = (newName || "").trim();
    if (!cleanNewName) {
      showToast("Имя спикера не может быть пустым", "error");
      return;
    }

    const oldName = this.targetOldSpeaker;
    if (!oldName) {
      this.closeSpeakerRenameModal();
      return;
    }

    if (oldName === cleanNewName) {
      this.closeSpeakerRenameModal();
      return;
    }

    const saveBtn = this.shadowRoot.getElementById("saveSpeakerModalBtn");
    const btnText = this.shadowRoot.getElementById("saveSpeakerBtnText");
    if (saveBtn) saveBtn.disabled = true;
    if (btnText) btnText.textContent = "Сохранение...";

    try {
      const jobId = this.currentJobId;
      if (jobId) {
        const res = await fetch(`/api/v1/transcription/jobs/${jobId}/speaker-rename`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            old_speaker_label: oldName,
            new_speaker_name: cleanNewName,
          }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || "Не удалось сохранить новое имя спикера.");
        }

        const updatedJob = await res.json();
        if (updatedJob.result) {
          globalStore.setState({ transcript: updatedJob.result });
          showToast(`Спикер «${oldName}» успешно переименован в «${cleanNewName}»`, "success");
        }
      } else {
        // Local in-memory rename
        const current = globalStore.state.transcript;
        if (current && current.utterances) {
          const cloned = JSON.parse(JSON.stringify(current));
          cloned.utterances.forEach((u) => {
            if (u.speaker === oldName) {
              u.speaker = cleanNewName;
            }
          });
          globalStore.setState({ transcript: cloned });
          showToast(`Спикер «${oldName}» переименован в «${cleanNewName}»`, "success");
        }
      }

      this.closeSpeakerRenameModal();
    } catch (err) {
      console.error("[TranscriptPlayer] Speaker rename error:", err);
      showToast(err.message || "Ошибка при переименовании спикера", "error");
    } finally {
      if (saveBtn) saveBtn.disabled = false;
      if (btnText) btnText.textContent = "Сохранить";
    }
  }

  handleStateUpdate(state) {
    const structuralChange =
      state.jobId !== this.currentJobId ||
      state.status !== this.currentStatus ||
      state.transcript !== this.currentTranscript;

    if (structuralChange) {
      this.currentJobId = state.jobId;
      this.currentStatus = state.status;
      this.currentTranscript = state.transcript;
      this.activeWordSpans.clear();
      this.render(state);
    }
  }

  updateActiveWords(currentTime) {
    const wordSpans = this.shadowRoot.querySelectorAll(".word-span");
    const nextActiveSpans = new Set();

    wordSpans.forEach((span) => {
      const start = parseFloat(span.getAttribute("data-start"));
      const end = parseFloat(span.getAttribute("data-end"));
      if (!isNaN(start) && !isNaN(end) && currentTime >= start && currentTime <= end) {
        nextActiveSpans.add(span);
      }
    });

    // Remove active class from spans that are no longer active
    this.activeWordSpans.forEach((span) => {
      if (!nextActiveSpans.has(span)) {
        span.classList.remove("active");
      }
    });

    // Add active class to newly active spans
    nextActiveSpans.forEach((span) => {
      if (!this.activeWordSpans.has(span)) {
        span.classList.add("active");
      }
    });

    this.activeWordSpans = nextActiveSpans;
  }

  /**
   * Ctrl+F style search logic
   */
  performCtrlFSearch(query) {
    this.searchQuery = (query || "").trim().toLowerCase();

    // Debounce updating the URL query param ?q=
    clearTimeout(this._searchUrlDebounce);
    this._searchUrlDebounce = setTimeout(() => {
      if (router.currentRoute?.pattern?.includes("/jobs/") || router.currentRoute?.pattern?.includes("/transcriptions/")) {
        router.updateQueryParams({ q: this.searchQuery || null }, { replace: true });
      }
    }, 400);

    // Reset previous search highlights
    const allSpans = this.shadowRoot.querySelectorAll(".word-span");
    allSpans.forEach((span) => {
      span.classList.remove("search-highlight", "search-highlight-active");
    });

    this.searchResults = [];
    this.currentMatchIndex = -1;

    if (!this.searchQuery) {
      this.updateSearchUI();
      return;
    }

    // Find all matching word spans
    allSpans.forEach((span) => {
      const wordText = span.textContent.toLowerCase();
      if (wordText.includes(this.searchQuery)) {
        span.classList.add("search-highlight");
        this.searchResults.push(span);
      }
    });

    if (this.searchResults.length > 0) {
      this.currentMatchIndex = 0;
      this.focusMatch(0);
    }

    this.updateSearchUI();
  }

  focusMatch(index) {
    if (this.searchResults.length === 0 || index < 0 || index >= this.searchResults.length) return;

    this.searchResults.forEach((el) => el.classList.remove("search-highlight-active"));

    const activeEl = this.searchResults[index];
    activeEl.classList.add("search-highlight-active");
    activeEl.scrollIntoView({ behavior: "smooth", block: "center" });

    this.updateSearchCounter();
  }

  navigateSearch(direction) {
    if (this.searchResults.length === 0) return;

    if (direction === "next") {
      this.currentMatchIndex = (this.currentMatchIndex + 1) % this.searchResults.length;
    } else if (direction === "prev") {
      this.currentMatchIndex = (this.currentMatchIndex - 1 + this.searchResults.length) % this.searchResults.length;
    }

    this.focusMatch(this.currentMatchIndex);
  }

  updateSearchUI() {
    const counterEl = this.shadowRoot.querySelector("#searchCounter");
    const prevBtn = this.shadowRoot.querySelector("#searchPrevBtn");
    const nextBtn = this.shadowRoot.querySelector("#searchNextBtn");

    if (counterEl) {
      if (!this.searchQuery) {
        counterEl.textContent = "";
      } else if (this.searchResults.length === 0) {
        counterEl.textContent = "0 из 0";
      } else {
        counterEl.textContent = `${this.currentMatchIndex + 1} из ${this.searchResults.length}`;
      }
    }

    const hasMatches = this.searchResults.length > 0;
    if (prevBtn) prevBtn.disabled = !hasMatches;
    if (nextBtn) nextBtn.disabled = !hasMatches;
  }

  updateSearchCounter() {
    const counterEl = this.shadowRoot.querySelector("#searchCounter");
    if (counterEl && this.searchResults.length > 0) {
      counterEl.textContent = `${this.currentMatchIndex + 1} из ${this.searchResults.length}`;
    }
  }

  render(state) {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--font-sans, system-ui, -apple-system, sans-serif);
          color: var(--text-primary, #f8fafc);
          box-sizing: border-box;
        }

        .player-card {
          background: var(--bg-glass-card, rgba(15, 23, 42, 0.8));
          backdrop-filter: blur(16px);
          -webkit-backdrop-filter: blur(16px);
          border: 1px solid var(--border-color-card, rgba(255, 255, 255, 0.12));
          border-radius: var(--radius-lg, 20px);
          padding: 24px;
          box-shadow: var(--shadow-md, 0 10px 30px rgba(0, 0, 0, 0.35));
          box-sizing: border-box;
          overflow: hidden;
        }

        .header-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 16px;
          margin-bottom: 20px;
          padding-bottom: 16px;
          border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
          width: 100%;
          box-sizing: border-box;
        }

        .header-title {
          font-size: 1.15rem;
          font-weight: 800;
          color: var(--text-primary, #f8fafc);
          letter-spacing: -0.02em;
          display: flex;
          align-items: center;
          gap: 12px;
          flex-wrap: wrap;
        }

        .lang-badge {
          font-size: 0.75rem;
          font-weight: 700;
          padding: 3px 10px;
          border-radius: 9999px;
          background: var(--primary-light, rgba(99, 102, 241, 0.15));
          color: var(--primary, #818cf8);
          border: 1px solid rgba(99, 102, 241, 0.3);
          text-transform: uppercase;
        }

        /* Ctrl+F Search Bar Container */
        .search-container {
          display: flex;
          align-items: center;
          gap: 8px;
          background: var(--bg-surface-elevated, rgba(255, 255, 255, 0.05));
          border: 1px solid var(--border-color, rgba(255, 255, 255, 0.12));
          border-radius: var(--radius-md, 12px);
          padding: 5px 10px;
          transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }

        .search-container:focus-within {
          border-color: var(--primary, #6366f1);
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
        }

        .search-input {
          background: transparent;
          border: none;
          color: var(--text-primary, #f8fafc);
          font-size: 0.85rem;
          font-family: var(--font-sans);
          outline: none;
          width: 180px;
        }

        .search-icon {
          width: 16px;
          height: 16px;
          color: var(--text-muted, #64748b);
          flex-shrink: 0;
        }

        .search-counter {
          font-family: var(--font-mono, monospace);
          font-size: 0.75rem;
          font-weight: 600;
          color: var(--primary, #818cf8);
          white-space: nowrap;
          user-select: none;
        }

        .search-nav-btn {
          width: 24px;
          height: 24px;
          border-radius: 6px;
          border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
          background: var(--bg-card-subtle, rgba(255, 255, 255, 0.05));
          color: var(--text-primary, #f8fafc);
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: all 0.15s ease;
          padding: 0;
          font-size: 0.75rem;
          flex-shrink: 0;
        }

        .search-nav-btn:hover:not(:disabled) {
          background: var(--primary-light, rgba(99, 102, 241, 0.25));
          border-color: var(--primary);
          color: var(--text-primary);
        }

        .search-nav-btn:disabled {
          opacity: 0.3;
          cursor: not-allowed;
        }

        /* Search Highlights */
        .word-span.search-highlight {
          background: rgba(245, 158, 11, 0.3);
          color: var(--text-primary);
          border-radius: 3px;
          padding: 1px 2px;
          border: 1px solid rgba(245, 158, 11, 0.5);
        }

        .word-span.search-highlight-active {
          background: #f59e0b !important;
          color: #000000 !important;
          font-weight: 800 !important;
          box-shadow: 0 0 12px #f59e0b !important;
          border: 1px solid #fef08a !important;
        }

        /* Audio Player Bar */
        .audio-player-card {
          position: sticky;
          top: 16px;
          z-index: 10;
          background: var(--bg-surface-elevated, #1e293b);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          padding: 12px 16px;
          border-radius: var(--radius-md, 14px);
          margin-bottom: 24px;
          border: 1px solid var(--border-color, rgba(255, 255, 255, 0.12));
          box-shadow: var(--shadow-md);
        }

        audio {
          width: 100%;
          height: 38px;
          outline: none;
        }

        /* Export Bar */
        .export-bar {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-bottom: 20px;
        }

        .export-btn {
          background: var(--bg-surface-elevated, rgba(255, 255, 255, 0.05));
          border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
          padding: 7px 14px;
          border-radius: var(--radius-sm, 8px);
          cursor: pointer;
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--text-primary, #f8fafc);
          display: inline-flex;
          align-items: center;
          gap: 6px;
          transition: all 0.2s ease;
          user-select: none;
        }

        .export-btn:hover {
          background: var(--bg-surface-hover, rgba(255, 255, 255, 0.1));
          border-color: var(--border-color-hover);
          transform: translateY(-1px);
        }

        /* Speakers Management Toolbar */
        .speakers-bar {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 10px;
          margin-bottom: 20px;
          padding: 10px 14px;
          background: var(--bg-surface-elevated, rgba(255, 255, 255, 0.04));
          border: 1px solid var(--border-color, rgba(255, 255, 255, 0.08));
          border-radius: var(--radius-md, 12px);
        }

        .speakers-label {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 0.8rem;
          font-weight: 700;
          color: var(--text-secondary, #94a3b8);
          text-transform: uppercase;
          letter-spacing: 0.03em;
        }

        .speaker-chips-list {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;
        }

        .speaker-chip-btn {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 0.825rem;
          font-weight: 700;
          padding: 5px 12px;
          border-radius: 9999px;
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
          user-select: none;
        }

        .speaker-chip-btn:hover {
          transform: translateY(-1px) scale(1.03);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
          filter: brightness(1.15);
        }

        .speaker-chip-btn .edit-icon {
          opacity: 0.7;
          transition: opacity 0.15s ease;
        }

        .speaker-chip-btn:hover .edit-icon {
          opacity: 1;
        }

        /* Utterance Blocks */
        .transcript-container {
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        .utterance-block {
          background: var(--bg-card-subtle, rgba(255, 255, 255, 0.03));
          border: 1px solid var(--border-color, rgba(255, 255, 255, 0.08));
          border-radius: var(--radius-md, 14px);
          padding: 16px 20px;
          transition: background 0.2s ease, border-color 0.2s ease;
        }

        .utterance-block:hover {
          background: var(--bg-surface-elevated, rgba(255, 255, 255, 0.06));
          border-color: var(--border-color-hover);
        }

        .speaker-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 10px;
        }

        .speaker-tag {
          font-weight: 700;
          font-size: 0.825rem;
          padding: 4px 12px;
          border-radius: 9999px;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          user-select: none;
        }

        .speaker-tag-clickable {
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .speaker-tag-clickable:hover {
          transform: scale(1.03);
          filter: brightness(1.15);
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        }

        .speaker-tag-clickable .edit-mini-icon {
          opacity: 0.6;
          transition: opacity 0.15s ease;
        }

        .speaker-tag-clickable:hover .edit-mini-icon {
          opacity: 1;
        }

        /* Speaker Rename Modal */
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          width: 100vw;
          height: 100vh;
          background: rgba(3, 7, 18, 0.78);
          backdrop-filter: blur(8px);
          -webkit-backdrop-filter: blur(8px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 99999;
          opacity: 0;
          visibility: hidden;
          pointer-events: none;
          transition: opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1), visibility 0.2s cubic-bezier(0.4, 0, 0.2, 1);
          padding: 20px;
          box-sizing: border-box;
        }

        .modal-overlay.open {
          opacity: 1;
          visibility: visible;
          pointer-events: auto;
        }

        .modal-card {
          background: var(--bg-surface-elevated, #1e293b);
          border: 1px solid var(--border-color, rgba(255, 255, 255, 0.16));
          border-radius: var(--radius-lg, 18px);
          padding: 26px;
          width: 100%;
          max-width: 450px;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
          transform: scale(0.96) translateY(8px);
          transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
          color: var(--text-primary, #f8fafc);
          box-sizing: border-box;
        }

        .modal-overlay.open .modal-card {
          transform: scale(1) translateY(0);
        }

        .modal-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 12px;
        }

        .modal-title {
          font-size: 1.15rem;
          font-weight: 800;
          margin: 0;
          color: var(--text-primary, #f8fafc);
        }

        .modal-close-btn {
          background: transparent;
          border: none;
          color: var(--text-muted, #94a3b8);
          cursor: pointer;
          font-size: 1.35rem;
          line-height: 1;
          padding: 4px 8px;
          border-radius: 6px;
          transition: color 0.15s ease, background 0.15s ease;
        }

        .modal-close-btn:hover {
          color: var(--text-primary, #f8fafc);
          background: rgba(255, 255, 255, 0.08);
        }

        .modal-desc {
          font-size: 0.875rem;
          color: var(--text-secondary, #94a3b8);
          margin-bottom: 16px;
          line-height: 1.5;
        }

        .modal-desc #modalOldSpeakerName {
          font-weight: 700;
          color: var(--primary, #818cf8);
        }

        .modal-input-group {
          margin-bottom: 14px;
        }

        .modal-input {
          width: 100%;
          box-sizing: border-box;
          background: var(--bg-card-subtle, rgba(255, 255, 255, 0.06));
          border: 1px solid var(--border-color, rgba(255, 255, 255, 0.15));
          border-radius: var(--radius-md, 10px);
          padding: 10px 14px;
          color: var(--text-primary, #f8fafc);
          font-size: 0.95rem;
          font-family: inherit;
          outline: none;
          transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }

        .modal-input:focus {
          border-color: var(--primary, #6366f1);
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
        }

        .suggestions-title {
          font-size: 0.75rem;
          font-weight: 700;
          color: var(--text-muted, #94a3b8);
          margin-bottom: 6px;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        .suggestions-chips {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-bottom: 20px;
        }

        .suggestion-chip {
          background: var(--bg-card-subtle, rgba(255, 255, 255, 0.06));
          border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
          color: var(--text-secondary, #cbd5e1);
          padding: 4px 10px;
          border-radius: 9999px;
          font-size: 0.75rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.15s ease;
          user-select: none;
        }

        .suggestion-chip:hover {
          background: var(--primary-light, rgba(99, 102, 241, 0.2));
          border-color: var(--primary, #6366f1);
          color: var(--text-primary, #ffffff);
          transform: translateY(-1px);
        }

        .modal-actions {
          display: flex;
          justify-content: flex-end;
          gap: 10px;
        }

        .modal-btn {
          padding: 9px 18px;
          border-radius: var(--radius-sm, 8px);
          font-size: 0.875rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s ease;
          border: none;
          font-family: inherit;
        }

        .modal-btn-cancel {
          background: var(--bg-card-subtle, rgba(255, 255, 255, 0.06));
          border: 1px solid var(--border-color, rgba(255, 255, 255, 0.12));
          color: var(--text-primary, #f8fafc);
        }

        .modal-btn-cancel:hover {
          background: rgba(255, 255, 255, 0.1);
        }

        .modal-btn-primary {
          background: var(--primary-gradient, linear-gradient(135deg, #6366f1, #a855f7));
          color: #ffffff;
          box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
        }

        .modal-btn-primary:hover:not(:disabled) {
          opacity: 0.95;
          transform: translateY(-1px);
        }

        .modal-btn-primary:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .time-badge {
          font-family: var(--font-mono, monospace);
          font-size: 0.75rem;
          color: var(--text-muted, #64748b);
          background: var(--bg-card-subtle, rgba(255, 255, 255, 0.04));
          padding: 3px 8px;
          border-radius: 4px;
        }

        .word-span {
          padding: 2px 4px;
          border-radius: 4px;
          cursor: pointer;
          transition: background 0.15s ease, color 0.15s ease;
          display: inline-block;
        }

        .word-span:hover {
          background: var(--primary-light, rgba(99, 102, 241, 0.25));
          color: var(--text-primary);
        }

        .word-span.active {
          background: var(--primary-gradient, linear-gradient(135deg, #6366f1, #a855f7)) !important;
          color: #ffffff !important;
          font-weight: 700 !important;
          box-shadow: 0 0 10px rgba(99, 102, 241, 0.5) !important;
        }

        .utterance-text {
          outline: none;
          line-height: 1.75;
          font-size: 0.925rem;
          color: var(--text-primary, #f8fafc);
          user-select: text;
        }

        .loading-container {
          text-align: center;
          padding: 48px 20px;
        }

        .progress-bar-bg {
          width: 100%;
          max-width: 400px;
          margin: 16px auto 8px;
          height: 8px;
          background: var(--bg-surface-elevated, rgba(255, 255, 255, 0.1));
          border-radius: 4px;
          overflow: hidden;
        }

        .progress-bar-fill {
          height: 100%;
          background: var(--primary-gradient);
          transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .empty-state {
          text-align: center;
          padding: 56px 20px;
          color: var(--text-muted, #64748b);
        }
      </style>

      <div class="player-card">
        ${this.renderStateContent(state)}
      </div>

      ${this.renderSpeakerRenameModal()}
    `;

    this.attachEventListeners(state);
  }

  renderStateContent(state) {
    if (state.status === "LOADING") {
      const clampedPercent = Math.min(Math.max(state.progress || 0, 0), 100);
      return `
        <div class="loading-container">
          <h3 style="color: var(--text-primary); margin-bottom: 8px; font-weight: 800;">
            ИИ Выполняет Диаризацию и Распознавание Речи...
          </h3>
          <p id="loadingStepMessage" style="color: var(--text-secondary); font-size: 0.875rem;">
            ${state.stepMessage || "Анализ аудиопотока в процессе..."}
          </p>
          <div class="progress-bar-bg">
            <div id="loadingProgressBarFill" class="progress-bar-fill" style="width: ${clampedPercent}%"></div>
          </div>
          <span id="loadingProgressPercent" style="font-family: var(--font-mono); font-size: 0.85rem; color: var(--primary); font-weight: 600;">
            ${Math.round(clampedPercent)}%
          </span>
        </div>
      `;
    }

    if (state.status === "ERROR") {
      return `
        <div class="empty-state">
          <h3 style="color: var(--accent-danger); margin-bottom: 8px;">Ошибка Обработки Аудио</h3>
          <p style="font-size: 0.875rem;">${state.errorMessage || "Произошла ошибка во время обработки стенограммы."}</p>
        </div>
      `;
    }

    if (state.status === "IDLE" || !state.transcript) {
      return `
        <div class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" style="margin-bottom:12px; opacity:0.4;">
            <path d="M12 1a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
            <line x1="12" y1="19" x2="12" y2="22"></line>
          </svg>
          <h3 style="color: var(--text-primary); margin-bottom: 6px; font-weight: 800;">
            ${state.status === "SUCCESS" ? "Стенограмма пуста" : "Стенограмма Пока Не Сформирована"}
          </h3>
          <p style="font-size: 0.875rem; max-width: 440px; margin: 0 auto; line-height: 1.6;">
            ${
              state.status === "SUCCESS"
                ? "В обработанной аудиозаписи не найдено реплик или аудиофрагментов."
                : "Загрузите аудиофайл в левой панели, чтобы получить синхронизированную расшифровку по репликам и спикерам."
            }
          </p>
        </div>
      `;
    }

    const utterances = state.transcript.utterances || [];
    const speakers = this.getUniqueSpeakers(utterances);
    const audioUrl = state.jobId ? `/api/v1/transcription/jobs/${state.jobId}/audio` : "";
    const lang = (state.transcript.detected_language || "ru").toUpperCase();
    const displayTitle =
      state.transcript.analysis?.title ||
      state.transcript.title ||
      "Интерактивная Стенограмма";
    const generatedTimestamp = state.transcript.analysis?.timestamp || "";

    return `
      <div class="header-bar">
        <div class="header-title">
          <span>${displayTitle}</span>
          <span class="lang-badge">Язык: ${lang}</span>
          ${generatedTimestamp ? `<span class="time-badge" style="font-size: 0.78rem; padding: 4px 10px;">${generatedTimestamp}</span>` : ""}
        </div>

        <div class="search-container">
          <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input
            type="text"
            class="search-input"
            id="transcriptSearch"
            placeholder="Поиск по стенограмме..."
            value="${this.searchQuery}"
          />
          <span class="search-counter" id="searchCounter"></span>
          <button class="search-nav-btn" id="searchPrevBtn" title="Предыдущее совпадение (Shift+Enter)" disabled>▲</button>
          <button class="search-nav-btn" id="searchNextBtn" title="Следующее совпадение (Enter)" disabled>▼</button>
        </div>
      </div>

      <div class="export-bar">
        <button class="export-btn" data-fmt="txt">Скачать TXT</button>
        <button class="export-btn" data-fmt="pdf">Скачать PDF</button>
        <button class="export-btn" data-fmt="docx">Скачать DOCX</button>
        <button class="export-btn" data-fmt="srt">Скачать SRT</button>
        <button class="export-btn" data-fmt="vtt">Скачать VTT</button>
        <button class="export-btn" data-fmt="json">Скачать JSON</button>
      </div>

      ${
        speakers.length > 0
          ? `
        <div class="speakers-bar">
          <span class="speakers-label">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block; vertical-align:middle;">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
              <circle cx="9" cy="7" r="4"></circle>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
            </svg>
            Спикеры:
          </span>
          <div class="speaker-chips-list">
            ${speakers
              .map((spk) => {
                const col = this.getSpeakerColor(spk);
                return `
                  <button
                    type="button"
                    class="speaker-chip-btn"
                    data-speaker-name="${spk}"
                    title="Нажмите, чтобы переименовать ${spk}"
                    style="background: ${col.bg}; color: ${col.text}; border: 1px solid ${col.border};"
                  >
                    <span class="speaker-chip-name">${spk}</span>
                    <svg class="edit-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                      <path d="M12 20h9"></path>
                      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                    </svg>
                  </button>
                `;
              })
              .join("")}
          </div>
        </div>
      `
          : ""
      }

      ${
        audioUrl
          ? `
        <div class="audio-player-card">
          <audio id="main-audio-player" controls src="${audioUrl}"></audio>
        </div>
      `
          : ""
      }

      <div class="transcript-container">
        ${utterances.map((utt) => this.renderUtterance(utt, state.currentTime)).join("")}
      </div>
    `;
  }

  renderSpeakerRenameModal() {
    return `
      <!-- Speaker Rename Modal Dialog -->
      <div class="modal-overlay" id="speakerRenameModalOverlay" role="dialog" aria-modal="true" aria-labelledby="speakerModalTitle">
        <div class="modal-card">
          <div class="modal-header">
            <h3 class="modal-title" id="speakerModalTitle">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block; vertical-align:-3px; margin-right:6px; color:var(--primary, #6366f1);">
                <path d="M12 20h9"></path>
                <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
              </svg>
              Переименовать спикера
            </h3>
            <button class="modal-close-btn" id="closeSpeakerModalBtn" aria-label="Закрыть">✕</button>
          </div>
          <p class="modal-desc">
            Заменит имя <span id="modalOldSpeakerName">«Спикер»</span> на новое имя во всей стенограмме и сохранит в базе данных.
          </p>
          <div class="modal-input-group">
            <input
              type="text"
              id="newSpeakerNameInput"
              class="modal-input"
              placeholder="Введите имя (например, Иван Иванов)"
              maxlength="100"
            />
          </div>
          <div class="suggestions-title">Быстрые варианты:</div>
          <div class="suggestions-chips">
            <button type="button" class="suggestion-chip" data-suggestion="Интервьюер">Интервьюер</button>
            <button type="button" class="suggestion-chip" data-suggestion="Респондент">Респондент</button>
            <button type="button" class="suggestion-chip" data-suggestion="Ведущий">Ведущий</button>
            <button type="button" class="suggestion-chip" data-suggestion="Клиент">Клиент</button>
            <button type="button" class="suggestion-chip" data-suggestion="Менеджер">Менеджер</button>
            <button type="button" class="suggestion-chip" data-suggestion="Спикер 1">Спикер 1</button>
            <button type="button" class="suggestion-chip" data-suggestion="Спикер 2">Спикер 2</button>
          </div>
          <div class="modal-actions">
            <button type="button" class="modal-btn modal-btn-cancel" id="cancelSpeakerModalBtn">Отмена</button>
            <button type="button" class="modal-btn modal-btn-primary" id="saveSpeakerModalBtn">
              <span id="saveSpeakerBtnText">Сохранить</span>
            </button>
          </div>
        </div>
      </div>
    `;
  }

  renderUtterance(utt, currentTime) {
    const color = this.getSpeakerColor(utt.speaker);
    return `
      <div class="utterance-block" data-utt-id="${utt.id}">
        <div class="speaker-header">
          <span
            class="speaker-tag speaker-tag-clickable"
            data-speaker="${utt.speaker}"
            title="Нажмите, чтобы переименовать спикера"
            style="background: ${color.bg}; color: ${color.text}; border: 1px solid ${color.border};"
          >
            <span>${utt.speaker}</span>
            <svg class="edit-mini-icon" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <path d="M12 20h9"></path>
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
            </svg>
          </span>
          <span class="time-badge">${utt.start.toFixed(1)}с — ${utt.end.toFixed(1)}с</span>
        </div>
        <div class="utterance-text" data-utt-id="${utt.id}">
          ${
            utt.words && utt.words.length > 0
              ? utt.words
                  .map((w) => {
                    const isActive = currentTime >= w.start && currentTime <= w.end;
                    return `<span class="word-span ${isActive ? "active" : ""}" data-start="${w.start}" data-end="${w.end}">${w.word}</span>`;
                  })
                  .join(" ")
              : utt.text
          }
        </div>
      </div>
    `;
  }

  attachEventListeners(state) {
    const audioEl = this.shadowRoot.querySelector("#main-audio-player");
    if (audioEl) {
      // Seek to initial audio time if hydrated from URL or state
      const initialTime = state.initialAudioTime || state.currentTime || 0;
      if (initialTime > 0) {
        const applySeek = () => {
          if (!isNaN(audioEl.duration) && audioEl.duration > 0) {
            audioEl.currentTime = Math.min(initialTime, audioEl.duration);
          }
        };
        audioEl.addEventListener("loadedmetadata", applySeek, { once: true });
        audioEl.addEventListener("canplay", applySeek, { once: true });
      }

      let lastTimeSync = 0;
      audioEl.addEventListener("timeupdate", () => {
        const now = Date.now();
        globalStore.setState({ currentTime: audioEl.currentTime });

        // Debounce URL timestamp update every 1.5 seconds during playback
        if (now - lastTimeSync > 1500) {
          lastTimeSync = now;
          if (router.currentRoute?.pattern?.includes("/jobs/") || router.currentRoute?.pattern?.includes("/transcriptions/")) {
            router.updateQueryParams(
              { t: Math.floor(audioEl.currentTime) > 0 ? Math.floor(audioEl.currentTime) : null },
              { replace: true }
            );
          }
        }
      });
    }

    // Ctrl+F Search Input & Navigation Events
    const searchInput = this.shadowRoot.querySelector("#transcriptSearch");
    const prevBtn = this.shadowRoot.querySelector("#searchPrevBtn");
    const nextBtn = this.shadowRoot.querySelector("#searchNextBtn");

    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        this.performCtrlFSearch(e.target.value);
      });

      searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          this.navigateSearch(e.shiftKey ? "prev" : "next");
        }
      });

      if (this.searchQuery) {
        this.performCtrlFSearch(this.searchQuery);
      }
    }

    if (prevBtn) {
      prevBtn.addEventListener("click", () => this.navigateSearch("prev"));
    }

    if (nextBtn) {
      nextBtn.addEventListener("click", () => this.navigateSearch("next"));
    }

    // Word timestamp click -> Seek audio
    this.shadowRoot.querySelectorAll(".word-span").forEach((wordEl) => {
      wordEl.addEventListener("click", (e) => {
        const startSec = parseFloat(e.target.getAttribute("data-start"));
        if (audioEl && !isNaN(startSec)) {
          audioEl.currentTime = startSec;
          audioEl.play();
        }
      });
    });

    // Multi-format export buttons
    this.shadowRoot.querySelectorAll(".export-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const fmt = e.target.getAttribute("data-fmt");
        if (state.jobId) {
          window.open(`/api/v1/transcription/jobs/${state.jobId}/export?export_format=${fmt}`, "_blank");
          showToast(`Экспорт в формате ${fmt.toUpperCase()} запущен`, "info");
        }
      });
    });

    // Speaker click -> Open rename modal
    this.shadowRoot.querySelectorAll(".speaker-chip-btn, .speaker-tag-clickable").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        const spkName = el.getAttribute("data-speaker-name") || el.getAttribute("data-speaker");
        if (spkName) {
          this.openSpeakerRenameModal(spkName);
        }
      });
    });

    // Speaker Rename Modal Listeners
    const modalOverlay = this.shadowRoot.getElementById("speakerRenameModalOverlay");
    const closeBtn = this.shadowRoot.getElementById("closeSpeakerModalBtn");
    const cancelBtn = this.shadowRoot.getElementById("cancelSpeakerModalBtn");
    const saveBtn = this.shadowRoot.getElementById("saveSpeakerModalBtn");
    const nameInput = this.shadowRoot.getElementById("newSpeakerNameInput");

    if (modalOverlay) {
      modalOverlay.addEventListener("click", (e) => {
        if (e.target === modalOverlay) {
          this.closeSpeakerRenameModal();
        }
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener("click", () => this.closeSpeakerRenameModal());
    }

    if (cancelBtn) {
      cancelBtn.addEventListener("click", () => this.closeSpeakerRenameModal());
    }

    if (saveBtn && nameInput) {
      saveBtn.addEventListener("click", () => {
        this.executeSpeakerRename(nameInput.value);
      });
    }

    if (nameInput) {
      nameInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          this.executeSpeakerRename(nameInput.value);
        } else if (e.key === "Escape") {
          e.preventDefault();
          this.closeSpeakerRenameModal();
        }
      });
    }

    // Quick suggestion chips
    this.shadowRoot.querySelectorAll(".suggestion-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const suggestion = chip.getAttribute("data-suggestion");
        if (suggestion && nameInput) {
          nameInput.value = suggestion;
          nameInput.focus();
        }
      });
    });
  }
}

customElements.define("transcript-player", TranscriptPlayer);
