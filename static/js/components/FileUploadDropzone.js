// filename: static/js/components/FileUploadDropzone.js
/**
 * High-Performance Drag-and-Drop File Upload Web Component
 * Features targeted DOM updates without layout thrashing or full re-renders,
 * dual-theme styling (Dark/Light), keyboard accessibility, and XHR progress tracking.
 */
import { globalStore, showToast, StorageHelper } from "../store.js";
import { router } from "../router.js";

export class FileUploadDropzone extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.isDragging = false;
    this.isUploading = false;
    this.uploadProgress = 0;
  }

  connectedCallback() {
    this.render();
    this.attachEvents();
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--font-sans, system-ui, -apple-system, sans-serif);
          color: var(--text-primary, #f8fafc);
        }

        .dropzone-card {
          position: relative;
          background: var(--bg-glass-card, rgba(15, 23, 42, 0.8));
          backdrop-filter: blur(16px);
          -webkit-backdrop-filter: blur(16px);
          border: 2px dashed var(--border-color, rgba(255, 255, 255, 0.15));
          border-radius: var(--radius-lg, 20px);
          padding: 36px 24px;
          text-align: center;
          cursor: pointer;
          transition: border-color 0.25s ease, background 0.25s ease, transform 0.2s ease, box-shadow 0.25s ease;
          box-shadow: var(--shadow-md, 0 10px 30px rgba(0, 0, 0, 0.3));
          overflow: hidden;
          outline: none;
        }

        .dropzone-card:hover {
          border-color: var(--primary, #6366f1);
          background: var(--bg-surface-elevated, rgba(30, 41, 59, 0.85));
          transform: translateY(-2px);
          box-shadow: var(--shadow-glow, 0 0 25px rgba(99, 102, 241, 0.25));
        }

        .dropzone-card.is-dragging {
          border-color: var(--primary, #6366f1) !important;
          background: var(--primary-light, rgba(99, 102, 241, 0.15)) !important;
          transform: scale(1.02);
          box-shadow: var(--shadow-glow, 0 0 30px rgba(99, 102, 241, 0.35));
        }

        .dropzone-card:focus-visible {
          outline: 2px solid var(--border-color-focus, #6366f1);
          outline-offset: 4px;
        }

        .icon-container {
          width: 64px;
          height: 64px;
          margin: 0 auto 16px;
          border-radius: var(--radius-md, 14px);
          background: var(--primary-light, rgba(99, 102, 241, 0.12));
          border: 1px solid rgba(99, 102, 241, 0.28);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--primary, #6366f1);
          transition: transform 0.25s ease, background 0.25s ease;
        }

        .dropzone-card:hover .icon-container,
        .dropzone-card.is-dragging .icon-container {
          transform: scale(1.08);
          background: rgba(99, 102, 241, 0.22);
        }

        .title {
          font-size: 1.05rem;
          font-weight: 700;
          color: var(--text-primary, #f8fafc);
          margin-bottom: 6px;
          letter-spacing: -0.01em;
        }

        .subtitle {
          font-size: 0.825rem;
          color: var(--text-secondary, #94a3b8);
          margin-bottom: 20px;
          line-height: 1.5;
        }

        .format-tags {
          display: flex;
          flex-wrap: wrap;
          justify-content: center;
          gap: 6px;
          margin-top: 14px;
        }

        .format-chip {
          font-family: var(--font-mono, monospace);
          font-size: 0.7rem;
          font-weight: 600;
          padding: 3px 8px;
          border-radius: 6px;
          background: var(--bg-card-subtle, rgba(255, 255, 255, 0.05));
          border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
          color: var(--text-secondary, #94a3b8);
          transition: border-color 0.2s ease, color 0.2s ease;
        }

        .dropzone-card:hover .format-chip {
          border-color: rgba(99, 102, 241, 0.3);
          color: var(--text-primary);
        }

        .file-input {
          display: none;
        }

        .progress-wrapper {
          margin-top: 20px;
          display: none;
        }

        .progress-wrapper.active {
          display: block;
        }

        .progress-bar-bg {
          width: 100%;
          height: 8px;
          background: var(--bg-surface-elevated, rgba(255, 255, 255, 0.1));
          border-radius: 4px;
          overflow: hidden;
        }

        .progress-bar-fill {
          height: 100%;
          width: 0%;
          background: var(--primary-gradient, linear-gradient(135deg, #6366f1, #a855f7));
          transition: width 0.2s ease-out;
          box-shadow: 0 0 12px rgba(99, 102, 241, 0.6);
        }

        .progress-status {
          display: flex;
          justify-content: space-between;
          font-size: 0.78rem;
          font-weight: 600;
          color: var(--primary, #818cf8);
          margin-top: 8px;
        }
      </style>

      <div
        class="dropzone-card"
        id="dropzone"
        tabindex="0"
        role="button"
        aria-label="Загрузить аудиозапись встречи. Нажмите или перетащите аудиофайл"
      >
        <div class="icon-container" aria-hidden="true">
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="17 8 12 3 7 8"></polyline>
            <line x1="12" y1="3" x2="12" y2="15"></line>
          </svg>
        </div>

        <div class="title">Загрузить аудиозапись встречи</div>
        <div class="subtitle">Перетащите сюда файл или нажмите для выбора</div>

        <div class="format-tags">
          <span class="format-chip">WAV</span>
          <span class="format-chip">MP3</span>
          <span class="format-chip">M4A</span>
          <span class="format-chip">FLAC</span>
          <span class="format-chip">OGG</span>
          <span class="format-chip">WEBM</span>
        </div>

        <input type="file" id="fileInput" class="file-input" accept="audio/*,.wav,.mp3,.m4a,.flac,.ogg,.webm" />

        <div class="progress-wrapper" id="progressWrapper">
          <div class="progress-bar-bg">
            <div class="progress-bar-fill" id="progressBarFill"></div>
          </div>
          <div class="progress-status">
            <span id="progressStatusLabel">Загрузка файла на сервер...</span>
            <span id="progressText">0%</span>
          </div>
        </div>
      </div>
    `;
  }

  attachEvents() {
    const dropzone = this.shadowRoot.querySelector("#dropzone");
    const fileInput = this.shadowRoot.querySelector("#fileInput");
    if (!dropzone || !fileInput) return;

    dropzone.addEventListener("click", () => fileInput.click());

    // Keyboard navigation (Enter or Space)
    dropzone.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        fileInput.click();
      }
    });

    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        this.handleFileUpload(e.target.files[0]);
      }
    });

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!this.isDragging) {
        this.isDragging = true;
        dropzone.classList.add("is-dragging");
      }
    });

    dropzone.addEventListener("dragleave", (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (this.isDragging) {
        this.isDragging = false;
        dropzone.classList.remove("is-dragging");
      }
    });

    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      e.stopPropagation();
      this.isDragging = false;
      dropzone.classList.remove("is-dragging");

      if (e.dataTransfer && e.dataTransfer.files.length > 0) {
        this.handleFileUpload(e.dataTransfer.files[0]);
      }
    });
  }

  updateProgress(percent, label = null) {
    this.uploadProgress = percent;
    const progressWrapper = this.shadowRoot.querySelector("#progressWrapper");
    const progressBarFill = this.shadowRoot.querySelector("#progressBarFill");
    const progressText = this.shadowRoot.querySelector("#progressText");
    const progressStatusLabel = this.shadowRoot.querySelector("#progressStatusLabel");

    if (progressWrapper) {
      if (this.isUploading) {
        progressWrapper.classList.add("active");
      } else {
        progressWrapper.classList.remove("active");
      }
    }

    if (progressBarFill) {
      progressBarFill.style.width = `${Math.min(Math.max(percent, 0), 100)}%`;
    }

    if (progressText) {
      progressText.textContent = `${Math.round(percent)}%`;
    }

    if (progressStatusLabel && label) {
      progressStatusLabel.textContent = label;
    }
  }

  async handleFileUpload(file) {
    if (!file) return;

    const allowedExtensions = ["wav", "mp3", "m4a", "flac", "ogg", "webm"];
    const ext = file.name.split(".").pop().toLowerCase();

    if (!allowedExtensions.includes(ext)) {
      showToast(
        `Формат .${ext} не поддерживается. Разрешены: WAV, MP3, M4A, FLAC, OGG, WEBM`,
        "error"
      );
      return;
    }

    // Check size limit: 500 MB
    const maxSizeMB = 500;
    if (file.size > maxSizeMB * 1024 * 1024) {
      showToast(`Размер файла превышает лимит ${maxSizeMB} МБ.`, "error");
      return;
    }

    this.isUploading = true;
    this.updateProgress(0, "Загрузка файла на сервер...");

    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/v1/transcription/upload", true);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        this.updateProgress(percent, "Загрузка файла на сервер...");
      }
    };

    xhr.onload = () => {
      if (xhr.status === 202) {
        this.updateProgress(100, "Файл загружен. Запуск распознавания...");
        setTimeout(() => {
          this.isUploading = false;
          this.updateProgress(0);
        }, 500);

        try {
          const response = JSON.parse(xhr.responseText);
          StorageHelper.saveActiveJob(response.job_id);
          globalStore.setState({
            jobId: response.job_id,
            status: "LOADING",
            progress: 5,
            stepMessage: "Аудиофайл принят. Инициализация ИИ-обработки...",
            errorMessage: null,
            transcript: null,
            currentTime: 0,
            initialAudioTime: 0,
            initialSearchQuery: "",
          });
          showToast("Файл передан на ИИ-обработку и диаризацию", "info");

          // Seamlessly transition URL to /jobs/:jobId
          router.navigate(`/jobs/${response.job_id}`, { replace: false });
        } catch (e) {
          showToast("Ошибка обработки ответа сервера", "error");
        }
      } else {
        this.isUploading = false;
        this.updateProgress(0);
        globalStore.setState({
          status: "ERROR",
          errorMessage: `Ошибка загрузки (Код HTTP ${xhr.status})`,
        });
        showToast(`Не удалось загрузить файл (Ошибка ${xhr.status})`, "error");
      }
    };

    xhr.onerror = () => {
      this.isUploading = false;
      this.updateProgress(0);
      globalStore.setState({
        status: "ERROR",
        errorMessage: "Сетевой сбой при отправке файла на сервер.",
      });
      showToast("Ошибка сети при отправке файла", "error");
    };

    xhr.send(formData);
  }
}

customElements.define("file-upload-dropzone", FileUploadDropzone);
