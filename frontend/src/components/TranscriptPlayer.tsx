import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Search,
  ChevronUp,
  ChevronDown,
  Download,
  Users,
  Edit2,
  Mic,
  AlertCircle,
  FileAudio,
} from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import { showToast } from "../store/toastStore";
import { api } from "../services/api";

const SPEAKER_PALETTE = [
  { bg: "rgba(99, 102, 241, 0.16)", text: "#818cf8", border: "rgba(99, 102, 241, 0.35)" },
  { bg: "rgba(16, 185, 129, 0.16)", text: "#10b981", border: "rgba(16, 185, 129, 0.35)" },
  { bg: "rgba(245, 158, 11, 0.16)", text: "#f59e0b", border: "rgba(245, 158, 11, 0.35)" },
  { bg: "rgba(236, 72, 153, 0.16)", text: "#ec4899", border: "rgba(236, 72, 153, 0.35)" },
  { bg: "rgba(6, 182, 212, 0.16)", text: "#06b6d4", border: "rgba(6, 182, 212, 0.35)" },
];

const SUGGESTIONS = [
  "Интервьюер",
  "Респондент",
  "Ведущий",
  "Клиент",
  "Менеджер",
  "Спикер 1",
  "Спикер 2",
];

export const TranscriptPlayer: React.FC = () => {
  const {
    jobId,
    status,
    progress,
    stepMessage,
    transcript,
    errorMessage,
    currentTime,
    initialAudioTime,
    initialSearchQuery,
    setCurrentTime,
    renameSpeakerInState,
  } = useAppStore();

  const audioRef = useRef<HTMLAudioElement>(null);
  const [searchQuery, setSearchQuery] = useState(initialSearchQuery || "");
  const [currentMatchIndex, setCurrentMatchIndex] = useState(-1);
  const [targetOldSpeaker, setTargetOldSpeaker] = useState<string | null>(null);
  const [newSpeakerName, setNewSpeakerName] = useState("");
  const [isRenaming, setIsRenaming] = useState(false);

  // Synchronize audio element initial seek
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const initialTime = initialAudioTime || currentTime || 0;
    if (initialTime > 0) {
      const applySeek = () => {
        if (!isNaN(audio.duration) && audio.duration > 0) {
          audio.currentTime = Math.min(initialTime, audio.duration);
        }
      };
      audio.addEventListener("loadedmetadata", applySeek, { once: true });
      audio.addEventListener("canplay", applySeek, { once: true });
    }
  }, [jobId]);

  // Compute speaker colors
  const getSpeakerColor = (speakerName?: string) => {
    let hash = 0;
    const name = speakerName || "Speaker";
    for (let i = 0; i < name.length; i++) {
      hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    const index = Math.abs(hash) % SPEAKER_PALETTE.length;
    return SPEAKER_PALETTE[index];
  };

  const utterances = transcript?.utterances || [];

  const uniqueSpeakers = useMemo(() => {
    const seen = new Set<string>();
    const res: string[] = [];
    utterances.forEach((u) => {
      const spk = u.speaker || "Спикер";
      if (!seen.has(spk)) {
        seen.add(spk);
        res.push(spk);
      }
    });
    return res;
  }, [utterances]);

  // Find search matches
  const searchMatches = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return [];

    const matches: { uttId: string; wordIdx: number; word: string }[] = [];
    utterances.forEach((u) => {
      if (u.words && u.words.length > 0) {
        u.words.forEach((w, wIdx) => {
          if (w.word.toLowerCase().includes(q)) {
            matches.push({ uttId: u.id, wordIdx: wIdx, word: w.word });
          }
        });
      } else if (u.text && u.text.toLowerCase().includes(q)) {
        matches.push({ uttId: u.id, wordIdx: -1, word: u.text });
      }
    });
    return matches;
  }, [utterances, searchQuery]);

  const handleSearchChange = (val: string) => {
    setSearchQuery(val);
    if (val.trim()) {
      setCurrentMatchIndex(0);
    } else {
      setCurrentMatchIndex(-1);
    }
  };

  const navigateSearch = (direction: "next" | "prev") => {
    if (searchMatches.length === 0) return;
    if (direction === "next") {
      setCurrentMatchIndex((prev) => (prev + 1) % searchMatches.length);
    } else {
      setCurrentMatchIndex((prev) => (prev - 1 + searchMatches.length) % searchMatches.length);
    }
  };

  const handleWordClick = (startSec: number) => {
    const audio = audioRef.current;
    if (audio && !isNaN(startSec)) {
      audio.currentTime = startSec;
      audio.play().catch(() => {});
    }
  };

  const handleExport = (format: string) => {
    if (!jobId) return;
    const url = api.transcription.getExportUrl(jobId, format);
    window.open(url, "_blank");
    showToast(`Экспорт в формате ${format.toUpperCase()} запущен`, "info");
  };

  const openSpeakerRenameModal = (speaker: string) => {
    setTargetOldSpeaker(speaker);
    setNewSpeakerName(speaker);
  };

  const closeSpeakerRenameModal = () => {
    setTargetOldSpeaker(null);
    setNewSpeakerName("");
  };

  const executeSpeakerRename = async () => {
    const cleanNewName = newSpeakerName.trim();
    if (!cleanNewName) {
      showToast("Имя спикера не может быть пустым", "error");
      return;
    }

    if (!targetOldSpeaker || targetOldSpeaker === cleanNewName) {
      closeSpeakerRenameModal();
      return;
    }

    setIsRenaming(true);
    try {
      if (jobId) {
        await api.transcription.renameSpeaker(jobId, targetOldSpeaker, cleanNewName);
      }
      renameSpeakerInState(targetOldSpeaker, cleanNewName);
      showToast(`Спикер «${targetOldSpeaker}» успешно переименован в «${cleanNewName}»`, "success");
      closeSpeakerRenameModal();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Ошибка при переименовании спикера";
      showToast(msg, "error");
    } finally {
      setIsRenaming(false);
    }
  };

  const displayTitle =
    transcript?.analysis?.title || transcript?.title || "Интерактивная Стенограмма";
  const lang = (transcript?.detected_language || "ru").toUpperCase();
  const audioUrl = jobId ? api.transcription.getAudioUrl(jobId) : "";

  return (
    <div className="bg-surface-elevated/60 border border-white/10 dark:border-white/10 light:border-slate-200 rounded-2xl p-6 md:p-7 shadow-sm">
      {status === "LOADING" && (
        <div className="text-center py-12 px-4">
          <h3 className="text-base md:text-lg font-bold text-text-primary mb-2">
            ИИ Выполняет Диаризацию и Распознавание Речи...
          </h3>
          <p className="text-xs md:text-sm text-text-secondary mb-4">
            {stepMessage || "Анализ аудиопотока в процессе..."}
          </p>
          <div className="w-full max-w-sm mx-auto h-2 rounded-full bg-white/10 overflow-hidden mb-2">
            <div
              className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 transition-[width] duration-200"
              style={{ width: `${Math.min(Math.max(progress, 0), 100)}%` }}
            />
          </div>
          <span className="font-mono text-xs font-semibold text-indigo-400">
            {Math.round(progress)}%
          </span>
        </div>
      )}

      {status === "ERROR" && (
        <div className="text-center py-12 px-4 text-text-muted">
          <AlertCircle className="w-12 h-12 mx-auto mb-3 text-red-400 opacity-80" />
          <h3 className="text-base font-bold text-red-400 mb-1">
            Ошибка Обработки Аудио
          </h3>
          <p className="text-xs md:text-sm max-w-md mx-auto">
            {errorMessage || "Произошла ошибка во время обработки стенограммы."}
          </p>
        </div>
      )}

      {(status === "IDLE" || !transcript) && status !== "LOADING" && status !== "ERROR" && (
        <div className="text-center py-14 px-4 text-text-muted">
          <FileAudio className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <h3 className="text-base font-bold text-text-primary mb-1">
            {status === "SUCCESS" ? "Стенограмма пуста" : "Стенограмма Пока Не Сформирована"}
          </h3>
          <p className="text-xs md:text-sm max-w-md mx-auto leading-relaxed">
            {status === "SUCCESS"
              ? "В обработанной аудиозаписи не найдено реплик или аудиофрагментов."
              : "Загрузите аудиофайл в панели слева, чтобы получить синхронизированную расшифровку по репликам и спикерам."}
          </p>
        </div>
      )}

      {status === "SUCCESS" && transcript && (
        <div>
          {/* Header Bar */}
          <div className="flex flex-wrap items-center justify-between gap-4 pb-4 mb-5 border-b border-white/10">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-base md:text-lg font-extrabold tracking-tight text-text-primary">
                {displayTitle}
              </span>
              <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full uppercase bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
                Язык: {lang}
              </span>
            </div>

            {/* Ctrl+F Search Bar */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/5 border border-white/10 focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20 transition-colors duration-150">
              <Search className="w-4 h-4 text-text-muted flex-shrink-0" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
                placeholder="Поиск по стенограмме..."
                className="bg-transparent border-none outline-none text-xs md:text-sm text-text-primary w-36 md:w-48 placeholder:text-text-muted"
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    navigateSearch(e.shiftKey ? "prev" : "next");
                  }
                }}
              />
              {searchQuery && (
                <span className="font-mono text-xs font-semibold text-indigo-400 whitespace-nowrap">
                  {searchMatches.length > 0
                    ? `${currentMatchIndex + 1} из ${searchMatches.length}`
                    : "0 из 0"}
                </span>
              )}
              <button
                type="button"
                disabled={searchMatches.length === 0}
                onClick={() => navigateSearch("prev")}
                className="w-6 h-6 rounded flex items-center justify-center bg-white/5 hover:bg-white/10 disabled:opacity-30 text-text-primary transition-colors duration-150 text-xs"
                title="Предыдущее совпадение (Shift+Enter)"
              >
                <ChevronUp className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                disabled={searchMatches.length === 0}
                onClick={() => navigateSearch("next")}
                className="w-6 h-6 rounded flex items-center justify-center bg-white/5 hover:bg-white/10 disabled:opacity-30 text-text-primary transition-colors duration-150 text-xs"
                title="Следующее совпадение (Enter)"
              >
                <ChevronDown className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Export Toolbar */}
          <div className="flex flex-wrap gap-2 mb-5">
            {["txt", "pdf", "docx", "srt", "vtt", "json"].map((fmt) => (
              <button
                key={fmt}
                type="button"
                onClick={() => handleExport(fmt)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-white/5 hover:bg-white/10 border border-white/10 text-text-primary transition-colors duration-150"
              >
                <Download className="w-3.5 h-3.5 text-indigo-400" />
                <span>Скачать {fmt.toUpperCase()}</span>
              </button>
            ))}
          </div>

          {/* Speakers Toolbar */}
          {uniqueSpeakers.length > 0 && (
            <div className="flex flex-wrap items-center gap-2.5 p-3 rounded-xl bg-white/5 border border-white/10 mb-5">
              <span className="inline-flex items-center gap-1.5 text-xs font-bold text-text-secondary uppercase tracking-wider">
                <Users className="w-3.5 h-3.5" />
                Спикеры:
              </span>
              <div className="flex flex-wrap gap-2">
                {uniqueSpeakers.map((spk) => {
                  const col = getSpeakerColor(spk);
                  return (
                    <button
                      key={spk}
                      type="button"
                      onClick={() => openSpeakerRenameModal(spk)}
                      title={`Нажмите, чтобы переименовать ${spk}`}
                      style={{
                        backgroundColor: col.bg,
                        color: col.text,
                        borderColor: col.border,
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border hover:opacity-85 transition-opacity duration-150 shadow-sm"
                    >
                      <span>{spk}</span>
                      <Edit2 className="w-3 h-3 opacity-70" />
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Audio Player Bar */}
          {audioUrl && (
            <div className="sticky top-4 z-20 p-3 rounded-xl bg-surface-elevated border border-white/15 shadow-md mb-6">
              <audio
                ref={audioRef}
                controls
                src={audioUrl}
                className="w-full h-10 rounded-lg outline-none"
                onTimeUpdate={() => {
                  if (audioRef.current) {
                    setCurrentTime(audioRef.current.currentTime);
                  }
                }}
              />
            </div>
          )}

          {/* Utterance Stream */}
          <div className="space-y-4">
            {utterances.map((utt) => {
              const col = getSpeakerColor(utt.speaker);
              const q = searchQuery.trim().toLowerCase();

              return (
                <div
                  key={utt.id}
                  className="p-4 md:p-5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 transition-colors duration-150"
                >
                  <div className="flex items-center justify-between mb-2.5">
                    <button
                      type="button"
                      onClick={() => openSpeakerRenameModal(utt.speaker)}
                      style={{
                        backgroundColor: col.bg,
                        color: col.text,
                        borderColor: col.border,
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full text-xs font-bold border hover:opacity-85 transition-opacity duration-150"
                      title="Нажмите для переименования"
                    >
                      <span>{utt.speaker}</span>
                      <Edit2 className="w-2.5 h-2.5 opacity-60" />
                    </button>
                    <span className="font-mono text-xs text-text-muted bg-white/5 px-2 py-0.5 rounded">
                      {utt.start.toFixed(1)}с — {utt.end.toFixed(1)}с
                    </span>
                  </div>

                  <div className="text-sm md:text-base text-text-primary leading-relaxed">
                    {utt.words && utt.words.length > 0 ? (
                      utt.words.map((w, wIdx) => {
                        const isActive =
                          currentTime >= w.start && currentTime <= w.end;
                        const isMatch =
                          q && w.word.toLowerCase().includes(q);
                        const matchIndex = searchMatches.findIndex(
                          (m) => m.uttId === utt.id && m.wordIdx === wIdx
                        );
                        const isFocusedMatch =
                          isMatch && matchIndex === currentMatchIndex;

                        return (
                          <span
                            key={wIdx}
                            onClick={() => handleWordClick(w.start)}
                            data-start={w.start}
                            data-end={w.end}
                            className={`word-span ${
                              isActive ? "active" : ""
                            } ${isMatch ? "search-highlight" : ""} ${
                              isFocusedMatch ? "search-highlight-active" : ""
                            }`}
                          >
                            {w.word}{" "}
                          </span>
                        );
                      })
                    ) : (
                      <span>{utt.text}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Speaker Rename Modal */}
      {targetOldSpeaker && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/80 animate-in fade-in duration-150"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeSpeakerRenameModal();
          }}
        >
          <div className="w-full max-w-md bg-surface-elevated border border-white/15 rounded-2xl p-6 shadow-xl text-text-primary">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-extrabold text-text-primary flex items-center gap-2">
                <Mic className="w-4 h-4 text-indigo-400" />
                Переименовать спикера
              </h3>
              <button
                type="button"
                onClick={closeSpeakerRenameModal}
                className="text-text-muted hover:text-text-primary text-lg leading-none"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-text-secondary mb-4 leading-relaxed">
              Заменит имя <span className="font-bold text-indigo-400">«{targetOldSpeaker}»</span> на новое имя во всей стенограмме.
            </p>

            <div className="mb-3">
              <input
                type="text"
                autoFocus
                value={newSpeakerName}
                onChange={(e) => setNewSpeakerName(e.target.value)}
                placeholder="Введите имя (например, Иван Иванов)"
                maxLength={100}
                onKeyDown={(e) => {
                  if (e.key === "Enter") executeSpeakerRename();
                  if (e.key === "Escape") closeSpeakerRenameModal();
                }}
                className="w-full px-3.5 py-2.5 rounded-xl bg-white/5 border border-white/15 text-sm text-text-primary outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
              />
            </div>

            <div className="text-[11px] font-bold text-text-muted uppercase tracking-wider mb-2">
              Быстрые варианты:
            </div>
            <div className="flex flex-wrap gap-1.5 mb-6">
              {SUGGESTIONS.map((sug) => (
                <button
                  key={sug}
                  type="button"
                  onClick={() => setNewSpeakerName(sug)}
                  className="px-2.5 py-1 rounded-full text-xs font-medium bg-white/5 hover:bg-indigo-500/20 hover:text-indigo-300 border border-white/10 text-text-secondary transition-colors duration-150"
                >
                  {sug}
                </button>
              ))}
            </div>

            <div className="flex justify-end gap-2.5">
              <button
                type="button"
                onClick={closeSpeakerRenameModal}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-white/5 hover:bg-white/10 border border-white/10 text-text-primary transition-colors duration-150"
              >
                Отмена
              </button>
              <button
                type="button"
                disabled={isRenaming}
                onClick={executeSpeakerRename}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-gradient-to-r from-indigo-500 to-purple-500 text-white shadow-sm hover:opacity-95 disabled:opacity-50 transition-opacity duration-150"
              >
                {isRenaming ? "Сохранение..." : "Сохранить"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
