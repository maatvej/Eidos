import React, { useState } from "react";
import {
  Sparkles,
  CheckCircle2,
  Copy,
  Check,
  AlertCircle,
  FileText,
  ListTodo,
} from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import { showToast } from "../store/toastStore";
import { ConversationAnalysis } from "../types";

export const ExecutiveIntelligenceCard: React.FC = () => {
  const { status, transcript, errorMessage } = useAppStore();
  const [copied, setCopied] = useState(false);

  const getEffectiveAnalysis = (): ConversationAnalysis | null => {
    if (!transcript) return null;
    if (transcript.analysis) return transcript.analysis;
    if (transcript.executive_summary) {
      const exec = transcript.executive_summary;
      return {
        title: "Исполнительная Аналитика",
        timestamp: "",
        executive_summary: typeof exec === "string" ? exec : exec.summary || "",
        key_decisions: typeof exec === "object" ? exec.key_decisions || [] : [],
        action_items: typeof exec === "object" ? exec.action_items || [] : [],
        overall_sentiment: typeof exec === "object" ? exec.sentiment || "NEUTRAL" : "NEUTRAL",
      };
    }
    return null;
  };

  const getRussianSentiment = (sentimentStr?: string) => {
    const raw = (sentimentStr || "").toUpperCase();
    if (raw.includes("POS") || raw.includes("ПОЗИ"))
      return {
        label: "Позитивный",
        className: "bg-emerald-500/15 text-emerald-400 border-emerald-500/35",
      };
    if (raw.includes("NEG") || raw.includes("НЕГА"))
      return {
        label: "Негативный",
        className: "bg-red-500/15 text-red-400 border-red-500/35",
      };
    return {
      label: "Нейтральный",
      className: "bg-slate-500/15 text-slate-400 border-slate-500/35",
    };
  };

  const getRussianPriority = (priorityStr?: string) => {
    const raw = (priorityStr || "").toUpperCase();
    if (raw === "HIGH" || raw === "ВЫСОКИЙ")
      return {
        label: "ВЫСОКИЙ",
        className: "bg-red-500/15 text-red-400 border-red-500/35",
      };
    if (raw === "MEDIUM" || raw === "СРЕДНИЙ")
      return {
        label: "СРЕДНИЙ",
        className: "bg-amber-500/15 text-amber-400 border-amber-500/35",
      };
    return {
      label: "НИЗКИЙ",
      className: "bg-emerald-500/15 text-emerald-400 border-emerald-500/35",
    };
  };

  const handleCopySummary = () => {
    const analysis = getEffectiveAnalysis();
    if (!analysis) return;

    const textToCopy = `=== EIDOS ИИ-АНАЛИТИКА ВСТРЕЧИ ===\n\n1. ГЛАВНЫЕ ТЕЗИСЫ:\n${
      analysis.executive_summary || ""
    }\n\n2. ПРИНЯТЫЕ РЕШЕНИЯ:\n${(analysis.key_decisions || [])
      .map((d) => `- ${d}`)
      .join("\n")}\n\n3. ЗАДАЧИ:\n${(analysis.action_items || [])
      .map(
        (a) =>
          `- [${getRussianPriority(a.priority).label}] ${a.task} (${
            a.owner || "Не назначен"
          })`
      )
      .join("\n")}`;

    navigator.clipboard
      .writeText(textToCopy)
      .then(() => {
        showToast("Выжимка скопирована в буфер обмена!", "success");
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      })
      .catch(() => {
        showToast("Не удалось скопировать в буфер обмена", "error");
      });
  };

  return (
    <div className="bg-glass border border-white/10 dark:border-white/10 light:border-slate-200 rounded-2xl p-6 md:p-7 backdrop-blur-xl shadow-lg transition-all duration-300 mb-6">
      {status === "LOADING" && (
        <div>
          <div className="flex items-center gap-3 pb-4 mb-4 border-b border-white/10">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Sparkles className="w-5 h-5 animate-spin" />
            </div>
            <h2 className="text-base font-bold text-text-primary">ИИ-Аналитика Встречи</h2>
          </div>
          <div className="space-y-3 py-2">
            <div className="skeleton-line w-[35%]" />
            <div className="skeleton-line w-full" />
            <div className="skeleton-line w-[92%]" />
            <div className="skeleton-line w-[78%]" />
            <div className="skeleton-line w-[60%] mt-6" />
            <div className="skeleton-line w-[85%]" />
          </div>
        </div>
      )}

      {status === "ERROR" && (
        <div className="text-center py-10 px-4 text-text-muted">
          <AlertCircle className="w-12 h-12 mx-auto mb-3 text-red-400 opacity-80" />
          <h2 className="text-base font-bold text-red-400 mb-1">
            Не удалось сформировать аналитику
          </h2>
          <p className="text-xs md:text-sm max-w-md mx-auto">
            {errorMessage || "Произошла ошибка при обработке данных встречи."}
          </p>
        </div>
      )}

      {(status === "IDLE" || (status === "SUCCESS" && !getEffectiveAnalysis())) && (
        <div className="text-center py-12 px-4 text-text-muted">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <h2 className="text-base font-bold text-text-primary mb-1">
            Исполнительная Выжимка Встречи
          </h2>
          <p className="text-xs md:text-sm max-w-md mx-auto leading-relaxed">
            Загрузите аудиозапись встречи, чтобы получить структурированное резюме, ключевые решения и поручения.
          </p>
        </div>
      )}

      {status === "SUCCESS" && getEffectiveAnalysis() && (
        <>
          {(() => {
            const analysis = getEffectiveAnalysis()!;
            const sentiment = getRussianSentiment(analysis.overall_sentiment);

            return (
              <div>
                {/* Header */}
                <div className="flex flex-wrap items-center justify-between gap-3 pb-4 mb-5 border-b border-white/10">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
                      <Sparkles className="w-5 h-5" />
                    </div>
                    <div>
                      <h2 className="text-base md:text-lg font-bold text-text-primary">
                        {analysis.title || "Исполнительная Аналитика Встречи"}
                      </h2>
                      {analysis.timestamp && (
                        <div className="text-xs text-text-muted mt-0.5">
                          {analysis.timestamp}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5">
                    <span
                      className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold border ${sentiment.className}`}
                    >
                      Тональность: {sentiment.label}
                    </span>
                    <button
                      type="button"
                      onClick={handleCopySummary}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-white/5 hover:bg-white/10 border border-white/10 text-text-primary transition-all active:scale-95"
                      title="Скопировать выжимку"
                    >
                      {copied ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Скопировано!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" />
                          <span>Скопировать</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Executive Summary */}
                <div className="text-xs font-extrabold uppercase tracking-wider text-indigo-400 flex items-center gap-2 mb-2">
                  <FileText className="w-3.5 h-3.5" />
                  Главные Тезисы и Резюме
                </div>
                <div className="text-sm text-text-primary leading-relaxed bg-white/5 border border-white/10 rounded-xl p-4 mb-6">
                  {analysis.executive_summary || "Резюме не сформировано"}
                </div>

                {/* Key Decisions */}
                <div className="text-xs font-extrabold uppercase tracking-wider text-indigo-400 flex items-center gap-2 mb-2">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Принятые Решения
                </div>
                <ul className="space-y-2 mb-6">
                  {analysis.key_decisions && analysis.key_decisions.length > 0 ? (
                    analysis.key_decisions.map((dec, idx) => (
                      <li
                        key={idx}
                        className="flex items-start gap-2.5 p-3 rounded-lg bg-white/5 border border-white/10 text-xs md:text-sm text-text-primary"
                      >
                        <span className="w-5 h-5 rounded-full bg-emerald-500/15 text-emerald-400 flex items-center justify-center flex-shrink-0 text-xs font-bold mt-0.5">
                          ✓
                        </span>
                        <span>{dec}</span>
                      </li>
                    ))
                  ) : (
                    <li className="p-3 rounded-lg bg-white/5 border border-white/10 text-xs text-text-muted">
                      Ключевые решения не выделены
                    </li>
                  )}
                </ul>

                {/* Action Items */}
                <div className="text-xs font-extrabold uppercase tracking-wider text-indigo-400 flex items-center gap-2 mb-2">
                  <ListTodo className="w-3.5 h-3.5" />
                  Задачи и Поручения (Action Items)
                </div>
                <div className="overflow-x-auto rounded-xl border border-white/10">
                  <table className="w-full text-left text-xs md:text-sm border-collapse">
                    <thead>
                      <tr className="bg-white/5 text-text-secondary uppercase text-[11px] font-bold tracking-wider border-b border-white/10">
                        <th className="py-2.5 px-4">Поручение / Задача</th>
                        <th className="py-2.5 px-4">Ответственный</th>
                        <th className="py-2.5 px-4">Срок</th>
                        <th className="py-2.5 px-4">Приоритет</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {analysis.action_items && analysis.action_items.length > 0 ? (
                        analysis.action_items.map((item, idx) => {
                          const priority = getRussianPriority(item.priority);
                          return (
                            <tr key={idx} className="hover:bg-white/5 transition-colors">
                              <td className="py-3 px-4 font-medium text-text-primary">
                                {item.task}
                              </td>
                              <td className="py-3 px-4 text-text-secondary">
                                {item.owner || "Не назначен"}
                              </td>
                              <td className="py-3 px-4 text-text-secondary">
                                {item.due_date || "—"}
                              </td>
                              <td className="py-3 px-4">
                                <span
                                  className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-extrabold border ${priority.className}`}
                                >
                                  {priority.label}
                                </span>
                              </td>
                            </tr>
                          );
                        })
                      ) : (
                        <tr>
                          <td
                            colSpan={4}
                            className="py-4 px-4 text-center text-text-muted text-xs"
                          >
                            Задачи не назначены
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })()}
        </>
      )}
    </div>
  );
};
