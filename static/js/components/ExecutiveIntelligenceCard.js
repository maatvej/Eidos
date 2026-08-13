// filename: static/js/components/ExecutiveIntelligenceCard.js
/**
 * Executive Intelligence Web Component rendering AI Meeting Analytics:
 * Executive Summary, Key Decisions, Action Items table, Sentiment & Priority badges, and Copy-to-Clipboard.
 * Optimized with subscription key filtering to prevent redundant re-renders during playback.
 */
import { globalStore, showToast } from "../store.js";

export class ExecutiveIntelligenceCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.unsubscribe = null;
    this.renderedStateKey = null;
  }

  connectedCallback() {
    this.unsubscribe = globalStore.subscribe(
      (state) => this.handleStateUpdate(state),
      ["status", "transcript", "errorMessage"]
    );
    this.render(globalStore.state);
  }

  disconnectedCallback() {
    if (this.unsubscribe) this.unsubscribe();
  }

  _getEffectiveAnalysis(state) {
    if (!state.transcript) return null;
    if (state.transcript.analysis) return state.transcript.analysis;
    if (state.transcript.executive_summary) {
      return {
        title: "Исполнительная Аналитика",
        timestamp: "",
        executive_summary:
          typeof state.transcript.executive_summary === "string"
            ? state.transcript.executive_summary
            : state.transcript.executive_summary.summary || "",
        key_decisions: state.transcript.executive_summary.key_decisions || [],
        action_items: state.transcript.executive_summary.action_items || [],
        overall_sentiment: state.transcript.executive_summary.sentiment || "NEUTRAL",
      };
    }
    return null;
  }

  handleStateUpdate(state) {
    const analysis = this._getEffectiveAnalysis(state);
    const stateKey = `${state.status}_${state.errorMessage}_${analysis ? JSON.stringify(analysis) : "empty"}`;
    if (this.renderedStateKey !== stateKey) {
      this.renderedStateKey = stateKey;
      this.render(state);
    }
  }

  render(state) {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--font-sans, system-ui, -apple-system, sans-serif);
          color: var(--text-primary, #f8fafc);
        }

        .card-container {
          background: var(--bg-glass-card, rgba(15, 23, 42, 0.8));
          backdrop-filter: blur(16px);
          -webkit-backdrop-filter: blur(16px);
          border: 1px solid var(--border-color-card, rgba(255, 255, 255, 0.12));
          border-radius: var(--radius-lg, 20px);
          padding: 28px;
          box-shadow: var(--shadow-md, 0 10px 30px rgba(0, 0, 0, 0.35));
          transition: border-color 0.25s ease;
        }

        .card-container:hover {
          border-color: var(--border-color-hover, rgba(255, 255, 255, 0.22));
        }

        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 24px;
          padding-bottom: 16px;
          border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
          flex-wrap: wrap;
          gap: 12px;
        }

        .header-left {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .header-icon {
          width: 40px;
          height: 40px;
          border-radius: var(--radius-md, 12px);
          background: var(--primary-light, rgba(99, 102, 241, 0.15));
          color: var(--primary, #6366f1);
          border: 1px solid rgba(99, 102, 241, 0.25);
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }

        .title {
          font-size: 1.15rem;
          font-weight: 800;
          color: var(--text-primary, #f8fafc);
          letter-spacing: -0.02em;
        }

        .actions-toolbar {
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
        }

        .sentiment-badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 5px 12px;
          border-radius: 9999px;
          font-size: 0.75rem;
          font-weight: 700;
          letter-spacing: 0.02em;
        }

        .sentiment-positive {
          background: rgba(16, 185, 129, 0.15);
          color: #10b981;
          border: 1px solid rgba(16, 185, 129, 0.35);
        }

        .sentiment-neutral {
          background: rgba(148, 163, 184, 0.15);
          color: var(--text-secondary, #94a3b8);
          border: 1px solid var(--border-color, rgba(148, 163, 184, 0.3));
        }

        .sentiment-negative {
          background: rgba(239, 68, 68, 0.15);
          color: #ef4444;
          border: 1px solid rgba(239, 68, 68, 0.35);
        }

        .section-title {
          font-size: 0.85rem;
          font-weight: 800;
          color: var(--primary, #818cf8);
          margin: 24px 0 12px;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .summary-box {
          font-size: 0.95rem;
          color: var(--text-primary, #f8fafc);
          line-height: 1.75;
          background: var(--bg-card-subtle, rgba(255, 255, 255, 0.03));
          border: 1px solid var(--border-color, rgba(255, 255, 255, 0.08));
          border-radius: var(--radius-md, 14px);
          padding: 18px 20px;
        }

        .decision-list {
          list-style: none;
          padding: 0;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .decision-item {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          padding: 12px 16px;
          border-radius: var(--radius-sm, 10px);
          background: var(--bg-card-subtle, rgba(255, 255, 255, 0.03));
          border: 1px solid var(--border-color, rgba(255, 255, 255, 0.08));
          font-size: 0.9rem;
          color: var(--text-primary, #f8fafc);
          transition: background 0.2s ease;
        }

        .decision-item:hover {
          background: var(--bg-surface-elevated, rgba(255, 255, 255, 0.06));
        }

        .check-icon {
          color: #10b981;
          background: rgba(16, 185, 129, 0.15);
          width: 22px;
          height: 22px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: bold;
          font-size: 0.75rem;
          flex-shrink: 0;
          margin-top: 1px;
        }

        .action-table-wrapper {
          overflow-x: auto;
          border-radius: var(--radius-md, 14px);
          border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
          margin-top: 12px;
        }

        .action-table {
          width: 100%;
          border-collapse: collapse;
          text-align: left;
        }

        .action-table th {
          background: var(--bg-surface-elevated, rgba(255, 255, 255, 0.05));
          padding: 12px 16px;
          font-size: 0.78rem;
          font-weight: 700;
          color: var(--text-secondary, #94a3b8);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
        }

        .action-table td {
          padding: 12px 16px;
          font-size: 0.875rem;
          color: var(--text-primary, #f8fafc);
          border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.06));
        }

        .action-table tr:last-child td {
          border-bottom: none;
        }

        .priority-pill {
          display: inline-block;
          padding: 3px 10px;
          border-radius: 9999px;
          font-size: 0.72rem;
          font-weight: 800;
          letter-spacing: 0.03em;
        }

        .priority-HIGH {
          background: rgba(239, 68, 68, 0.15);
          color: #ef4444;
          border: 1px solid rgba(239, 68, 68, 0.35);
        }

        .priority-MEDIUM {
          background: rgba(245, 158, 11, 0.15);
          color: #f59e0b;
          border: 1px solid rgba(245, 158, 11, 0.35);
        }

        .priority-LOW {
          background: rgba(16, 185, 129, 0.15);
          color: #10b981;
          border: 1px solid rgba(16, 185, 129, 0.35);
        }

        .ghost-button {
          background: var(--bg-surface-elevated, rgba(255, 255, 255, 0.06));
          border: 1px solid var(--border-color, rgba(255, 255, 255, 0.12));
          color: var(--text-primary, #f8fafc);
          padding: 7px 14px;
          border-radius: var(--radius-sm, 10px);
          font-size: 0.8rem;
          font-weight: 600;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          transition: all 0.2s ease;
          user-select: none;
        }

        .ghost-button:hover {
          background: var(--bg-surface-hover, rgba(255, 255, 255, 0.12));
          border-color: var(--border-color-hover);
          transform: translateY(-1px);
        }

        .ghost-button:active {
          transform: translateY(0);
        }

        .skeleton-line {
          height: 16px;
          background: linear-gradient(90deg, var(--bg-card-subtle) 25%, var(--bg-surface-elevated) 50%, var(--bg-card-subtle) 75%);
          background-size: 200% 100%;
          animation: shimmer 1.5s infinite;
          border-radius: 4px;
          margin-bottom: 12px;
        }

        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }

        .empty-container {
          text-align: center;
          padding: 48px 20px;
          color: var(--text-muted, #64748b);
        }

        .empty-icon {
          width: 52px;
          height: 52px;
          margin: 0 auto 16px;
          opacity: 0.45;
          color: var(--text-secondary, #94a3b8);
        }
      </style>

      <div class="card-container">
        ${this.renderStateContent(state)}
      </div>
    `;

    this.attachEventListeners(state);
  }

  getRussianSentiment(sentimentStr) {
    const raw = (sentimentStr || "").toUpperCase();
    if (raw.includes("POS") || raw.includes("ПОЗИ"))
      return { label: "Позитивный", css: "sentiment-positive" };
    if (raw.includes("NEG") || raw.includes("НЕГА"))
      return { label: "Негативный", css: "sentiment-negative" };
    return { label: "Нейтральный", css: "sentiment-neutral" };
  }

  getRussianPriority(priorityStr) {
    const raw = (priorityStr || "").toUpperCase();
    if (raw === "HIGH" || raw === "ВЫСОКИЙ")
      return { label: "ВЫСОКИЙ", css: "priority-HIGH" };
    if (raw === "MEDIUM" || raw === "СРЕДНИЙ")
      return { label: "СРЕДНИЙ", css: "priority-MEDIUM" };
    return { label: "НИЗКИЙ", css: "priority-LOW" };
  }

  renderStateContent(state) {
    if (state.status === "LOADING") {
      return `
        <div class="header">
          <div class="header-left">
            <div class="header-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
              </svg>
            </div>
            <div class="title">ИИ-Аналитика Встречи</div>
          </div>
        </div>
        <div style="padding: 10px 0;">
          <div class="skeleton-line" style="width: 35%;"></div>
          <div class="skeleton-line" style="width: 100%;"></div>
          <div class="skeleton-line" style="width: 92%;"></div>
          <div class="skeleton-line" style="width: 78%;"></div>
          <div class="skeleton-line" style="width: 60%; margin-top: 24px;"></div>
          <div class="skeleton-line" style="width: 85%;"></div>
        </div>
      `;
    }

    if (state.status === "ERROR") {
      return `
        <div class="empty-container">
          <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          <div class="title" style="margin-bottom: 8px;">Не удалось сформировать аналитику</div>
          <p style="font-size: 0.875rem;">${state.errorMessage || "Произошла ошибка при обработке данных встречи."}</p>
        </div>
      `;
    }

    const analysis = this._getEffectiveAnalysis(state);
    if (!analysis) {
      return `
        <div class="empty-container">
          <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="16" y1="13" x2="8" y2="13"></line>
            <line x1="16" y1="17" x2="8" y2="17"></line>
            <polyline points="10 9 9 9 8 9"></polyline>
          </svg>
          <div class="title" style="margin-bottom: 8px;">Исполнительная Выжимка Встречи</div>
          <p style="font-size: 0.875rem; max-width: 440px; margin: 0 auto; line-height: 1.6;">
            Загрузите аудиозапись встречи, чтобы получить структурированное резюме, ключевые решения и поручения.
          </p>
        </div>
      `;
    }
    const sentimentObj = this.getRussianSentiment(analysis.overall_sentiment);

    return `
      <div class="header">
        <div class="header-left">
          <div class="header-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
              <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
          </div>
          <div>
            <div class="title">${analysis.title || "Исполнительная Аналитика Встречи"}</div>
            ${analysis.timestamp ? `<div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">${analysis.timestamp}</div>` : ""}
          </div>
        </div>

        <div class="actions-toolbar">
          <span class="sentiment-badge ${sentimentObj.css}">
            Тональность: ${sentimentObj.label}
          </span>
          <button id="copySummaryBtn" class="ghost-button" type="button" title="Скопировать выжимку">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
            <span id="copyBtnText">Скопировать</span>
          </button>
        </div>
      </div>

      <div class="section-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="21" y1="10" x2="3" y2="10"></line>
          <line x1="21" y1="6" x2="3" y2="6"></line>
          <line x1="21" y1="14" x2="3" y2="14"></line>
          <line x1="21" y1="18" x2="3" y2="18"></line>
        </svg>
        Главные Тезисы и Резюме
      </div>
      <div class="summary-box">${analysis.executive_summary || "Резюме не сформировано"}</div>

      <div class="section-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
          <polyline points="22 4 12 14.01 9 11.01"></polyline>
        </svg>
        Принятые Решения
      </div>
      <ul class="decision-list">
        ${
          analysis.key_decisions && analysis.key_decisions.length > 0
            ? analysis.key_decisions
                .map(
                  (dec) => `
              <li class="decision-item">
                <span class="check-icon">✓</span>
                <span>${dec}</span>
              </li>
            `
                )
                .join("")
            : `<li class="decision-item" style="color: var(--text-muted);">Ключевые решения не выделены</li>`
        }
      </ul>

      <div class="section-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9 11 12 14 22 4"></polyline>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
        </svg>
        Задачи и Поручения (Action Items)
      </div>

      <div class="action-table-wrapper">
        <table class="action-table">
          <thead>
            <tr>
              <th>Поручение / Задача</th>
              <th>Ответственный</th>
              <th>Срок</th>
              <th>Приоритет</th>
            </tr>
          </thead>
          <tbody>
            ${
              analysis.action_items && analysis.action_items.length > 0
                ? analysis.action_items
                    .map((item) => {
                      const pObj = this.getRussianPriority(item.priority);
                      return `
                  <tr>
                    <td style="font-weight: 500;">${item.task}</td>
                    <td style="color: var(--text-secondary);">${item.owner || "Не назначен"}</td>
                    <td style="color: var(--text-secondary);">${item.due_date || "—"}</td>
                    <td><span class="priority-pill ${pObj.css}">${pObj.label}</span></td>
                  </tr>
                `;
                    })
                    .join("")
                : `<tr><td colspan="4" style="text-align:center; color: var(--text-muted);">Задачи не назначены</td></tr>`
            }
          </tbody>
        </table>
      </div>
    `;
  }

  attachEventListeners(state) {
    const copyBtn = this.shadowRoot.querySelector("#copySummaryBtn");
    const copyBtnText = this.shadowRoot.querySelector("#copyBtnText");

    if (copyBtn && state.transcript && state.transcript.analysis) {
      copyBtn.addEventListener("click", () => {
        const analysis = state.transcript.analysis;
        const textToCopy = `=== EIDOS ИИ-АНАЛИТИКА ВСТРЕЧИ ===\n\n1. ГЛАВНЫЕ ТЕЗИСЫ:\n${analysis.executive_summary || ""}\n\n2. ПРИНЯТЫЕ РЕШЕНИЯ:\n${(analysis.key_decisions || []).map((d) => `- ${d}`).join("\n")}\n\n3. ЗАДАЧИ:\n${(analysis.action_items || []).map((a) => `- [${this.getRussianPriority(a.priority).label}] ${a.task} (${a.owner || "Не назначен"})`).join("\n")}`;

        navigator.clipboard.writeText(textToCopy).then(() => {
          showToast("Выжимка скопирована в буфер обмена!", "success");
          if (copyBtnText) {
            copyBtnText.textContent = "Скопировано! ✓";
            setTimeout(() => {
              if (copyBtnText) copyBtnText.textContent = "Скопировать";
            }, 2000);
          }
        }).catch(() => {
          showToast("Не удалось скопировать в буфер обмена", "error");
        });
      });
    }
  }
}

customElements.define("executive-intelligence-card", ExecutiveIntelligenceCard);
