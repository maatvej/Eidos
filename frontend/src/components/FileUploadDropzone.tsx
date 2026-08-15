import React, { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import { useAppStore, StorageHelper } from "../store/useAppStore";
import { showToast } from "../store/toastStore";

const ALLOWED_EXTENSIONS = ["wav", "mp3", "m4a", "flac", "ogg", "webm"];
const MAX_FILE_SIZE_MB = 500;

export const FileUploadDropzone: React.FC = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [progressLabel, setProgressLabel] = useState("Загрузка файла на сервер...");

  const { setJobState, setCurrentRoute } = useAppStore();

  const handleFile = (file: File) => {
    if (!file) return;

    const ext = file.name.split(".").pop()?.toLowerCase() || "";
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      showToast(
        `Формат .${ext} не поддерживается. Разрешены: WAV, MP3, M4A, FLAC, OGG, WEBM`,
        "error"
      );
      return;
    }

    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      showToast(`Размер файла превышает лимит ${MAX_FILE_SIZE_MB} МБ.`, "error");
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);
    setProgressLabel("Загрузка файла на сервер...");

    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/v1/transcription/upload", true);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        setUploadProgress(percent);
      }
    };

    xhr.onload = () => {
      if (xhr.status === 202) {
        setUploadProgress(100);
        setProgressLabel("Файл загружен. Запуск распознавания...");

        setTimeout(() => {
          setIsUploading(false);
          setUploadProgress(0);
        }, 500);

        try {
          const response = JSON.parse(xhr.responseText);
          const newJobId = response.job_id;
          StorageHelper.saveActiveJob(newJobId);

          setJobState({
            jobId: newJobId,
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

          const targetUrl = `/jobs/${newJobId}`;
          window.history.pushState({}, "", targetUrl);
          setCurrentRoute(targetUrl);
        } catch {
          showToast("Ошибка обработки ответа сервера", "error");
        }
      } else {
        setIsUploading(false);
        setUploadProgress(0);
        setJobState({
          status: "ERROR",
          errorMessage: `Ошибка загрузки (Код HTTP ${xhr.status})`,
        });
        showToast(`Не удалось загрузить файл (Ошибка ${xhr.status})`, "error");
      }
    };

    xhr.onerror = () => {
      setIsUploading(false);
      setUploadProgress(0);
      setJobState({
        status: "ERROR",
        errorMessage: "Сетевой сбой при отправке файла на сервер.",
      });
      showToast("Ошибка сети при отправке файла", "error");
    };

    xhr.send(formData);
  };

  return (
    <div
      tabIndex={0}
      role="button"
      aria-label="Загрузить аудиозапись встречи. Нажмите или перетащите аудиофайл"
      onClick={() => fileInputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          fileInputRef.current?.click();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          handleFile(e.dataTransfer.files[0]);
        }
      }}
      className={`relative p-8 md:p-10 text-center rounded-2xl border-2 border-dashed transition-all duration-300 cursor-pointer overflow-hidden backdrop-blur-xl shadow-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
        isDragging
          ? "border-indigo-500 bg-indigo-500/15 scale-[1.02] shadow-indigo-500/20"
          : "border-white/15 hover:border-indigo-500 bg-glass hover:bg-surface-elevated hover:-translate-y-0.5"
      }`}
    >
      <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 transition-transform duration-300 group-hover:scale-110">
        <UploadCloud className="w-8 h-8" />
      </div>

      <h2 className="text-base md:text-lg font-bold text-text-primary mb-1">
        Загрузить аудиозапись встречи
      </h2>
      <p className="text-xs md:text-sm text-text-secondary mb-5">
        Перетащите сюда файл или нажмите для выбора
      </p>

      <div className="flex flex-wrap justify-center gap-1.5 mt-2">
        {ALLOWED_EXTENSIONS.map((ext) => (
          <span
            key={ext}
            className="font-mono text-[11px] font-semibold px-2 py-0.5 rounded-md bg-white/5 border border-white/10 text-text-secondary uppercase"
          >
            {ext}
          </span>
        ))}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*,.wav,.mp3,.m4a,.flac,.ogg,.webm"
        className="hidden"
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) {
            handleFile(e.target.files[0]);
          }
        }}
      />

      {isUploading && (
        <div className="mt-6 pt-4 border-t border-white/10">
          <div className="w-full h-2 rounded-full bg-surface-elevated overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-200 shadow-md shadow-indigo-500/50"
              style={{ width: `${Math.min(Math.max(uploadProgress, 0), 100)}%` }}
            />
          </div>
          <div className="flex justify-between items-center text-xs font-semibold text-indigo-400 mt-2">
            <span>{progressLabel}</span>
            <span>{uploadProgress}%</span>
          </div>
        </div>
      )}
    </div>
  );
};
