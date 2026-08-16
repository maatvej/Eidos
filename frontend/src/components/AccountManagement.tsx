import React, { useEffect, useState } from "react";
import {
  History,
  Shield,
  Search,
  RefreshCw,
  Trash2,
  ExternalLink,
  Copy,
  User,
  Key,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useAppStore } from "../store/useAppStore";
import { showToast } from "../store/toastStore";
import { api } from "../services/api";
import { AccountTranscriptionItem, UserProfile } from "../types";

export const AccountManagement: React.FC = () => {
  const { user, setUser, accountTab, setAccountTab, navigate } = useAppStore();

  const [profileData, setProfileData] = useState<UserProfile | null>(user);
  const [transcriptions, setTranscriptions] = useState<AccountTranscriptionItem[]>([]);
  const [pagination, setPagination] = useState({ page: 1, limit: 10, total: 0, total_pages: 1 });
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("-created_at");
  const [isLoading, setIsLoading] = useState(false);

  // Forms
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  // Modals
  const [detailItem, setDetailItem] = useState<AccountTranscriptionItem | null>(null);
  const [deleteCandidate, setDeleteCandidate] = useState<AccountTranscriptionItem | null>(null);

  // Load profile
  useEffect(() => {
    const controller = new AbortController();
    api.account
      .getProfile(controller.signal)
      .then((data) => {
        setProfileData(data);
        setUser(data);
        setFirstName(data.first_name || "");
        setLastName(data.last_name || "");
        setEmail(data.email || "");
      })
      .catch((err) => {
        if ((err as Error)?.name !== "AbortError") {
          console.error("Error loading profile:", err);
        }
      });

    return () => controller.abort();
  }, [setUser]);

  // Load transcriptions
  const loadTranscriptions = async (
    page = pagination.page,
    search = searchQuery,
    sort = sortBy,
    signal?: AbortSignal
  ) => {
    setIsLoading(true);
    try {
      const data = await api.account.getTranscriptions(
        {
          page,
          limit: pagination.limit,
          search: search || undefined,
          sort_by: sort,
        },
        signal
      );
      setTranscriptions(data.items);
      setPagination({
        page: data.page,
        limit: data.limit,
        total: data.total,
        total_pages: data.total_pages,
      });
    } catch (err: unknown) {
      if ((err as Error)?.name !== "AbortError") {
        console.error("Error loading transcriptions:", err);
        showToast("Ошибка при получении истории транскрипций", "error");
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    if (accountTab === "history") {
      loadTranscriptions(1, searchQuery, sortBy, controller.signal);
    }
    return () => controller.abort();
  }, [accountTab, sortBy]);

  // Keyboard shortcut listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setDetailItem(null);
        setDeleteCandidate(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const formatDuration = (seconds?: number) => {
    if (!seconds || isNaN(seconds)) return "00:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const formatDate = (isoString?: string) => {
    if (!isoString) return "—";
    const date = new Date(isoString);
    return date.toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getStatusBadge = (statusStr?: string) => {
    const s = (statusStr || "").toLowerCase();
    if (s === "completed") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/35">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          Готово
        </span>
      );
    }
    if (s === "processing") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/15 text-amber-400 border border-amber-500/35">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
          Обработка
        </span>
      );
    }
    if (s === "failed") {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-500/15 text-red-400 border border-red-500/35">
          <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
          Ошибка
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-500/15 text-slate-400 border border-slate-500/35">
        {statusStr || "В очереди"}
      </span>
    );
  };

  const handleOpenInStudio = (id: string) => {
    setDetailItem(null);
    navigate(`/jobs/${id}`);
  };

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const updated = await api.account.updateProfile({
        first_name: firstName,
        last_name: lastName,
        email,
      });
      setProfileData(updated);
      setUser(updated);
      showToast("Данные профиля успешно обновлены!", "success");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Ошибка при сохранении данных профиля";
      showToast(msg, "error");
    }
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      showToast("Новый пароль и подтверждение не совпадают", "error");
      return;
    }
    try {
      await api.account.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      showToast("Пароль успешно изменён!", "success");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Не удалось обновить пароль";
      showToast(msg, "error");
    }
  };

  const executeDelete = async () => {
    if (!deleteCandidate) return;
    const id = deleteCandidate.id;
    setDeleteCandidate(null);

    try {
      await api.account.deleteTranscription(id);
      showToast("Запись транскрипции успешно удалена", "success");
      setTranscriptions((prev) => prev.filter((t) => t.id !== id));
      loadTranscriptions(pagination.page);

      if (useAppStore.getState().jobId === id) {
        useAppStore.getState().resetJobState();
      }
    } catch {
      showToast("Ошибка при удалении транскрипции", "error");
    }
  };

  return (
    <div className="bg-white/90 dark:bg-surface-elevated/60 border border-slate-300 dark:border-white/10 rounded-2xl p-6 md:p-8 shadow-sm">
      {/* Navigation Tabs */}
      <div className="flex flex-wrap gap-2 md:gap-3 pb-4 mb-6 border-b border-slate-200 dark:border-white/10">
        <button
          type="button"
          onClick={() => setAccountTab("history", true)}
          className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs md:text-sm font-semibold transition-colors duration-150 ${
            accountTab === "history"
              ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-sm"
              : "bg-slate-100/80 hover:bg-slate-200 text-slate-700 border border-slate-300/80 dark:border-transparent dark:bg-transparent dark:text-text-secondary dark:hover:text-text-primary dark:hover:bg-white/5"
          }`}
        >
          <History className="w-4 h-4" />
          <span>История транскрипций</span>
        </button>

        <button
          type="button"
          onClick={() => setAccountTab("profile", true)}
          className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs md:text-sm font-semibold transition-colors duration-150 ${
            accountTab === "profile"
              ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-sm"
              : "bg-slate-100/80 hover:bg-slate-200 text-slate-700 border border-slate-300/80 dark:border-transparent dark:bg-transparent dark:text-text-secondary dark:hover:text-text-primary dark:hover:bg-white/5"
          }`}
        >
          <User className="w-4 h-4" />
          <span>Профиль</span>
        </button>

        <button
          type="button"
          onClick={() => setAccountTab("security", true)}
          className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs md:text-sm font-semibold transition-colors duration-150 ${
            accountTab === "security"
              ? "bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-sm"
              : "bg-slate-100/80 hover:bg-slate-200 text-slate-700 border border-slate-300/80 dark:border-transparent dark:bg-transparent dark:text-text-secondary dark:hover:text-text-primary dark:hover:bg-white/5"
          }`}
        >
          <Shield className="w-4 h-4" />
          <span>Безопасность и пароль</span>
        </button>
      </div>

      {/* History Tab */}
      {accountTab === "history" && (
        <div>
          {/* Controls Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
            <div className="flex-1 min-w-[240px] relative">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 dark:text-text-muted pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  loadTranscriptions(1, e.target.value, sortBy);
                }}
                placeholder="Поиск по названию транскрипции..."
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-white dark:bg-surface-elevated border border-slate-300 dark:border-white/10 text-xs md:text-sm text-text-primary outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 shadow-sm"
              />
            </div>

            <div className="flex items-center gap-2.5">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-3.5 py-2.5 rounded-xl bg-white dark:bg-surface-elevated border border-slate-300 dark:border-white/10 text-xs md:text-sm text-text-primary outline-none cursor-pointer shadow-sm"
              >
                <option value="-created_at">Сначала новые</option>
                <option value="created_at">Сначала старые</option>
                <option value="title">По названию (А-Я)</option>
                <option value="-duration_seconds">По длительности</option>
              </select>

              <button
                type="button"
                onClick={() => loadTranscriptions(pagination.page, searchQuery, sortBy)}
                className="p-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 border border-slate-300 dark:bg-surface-elevated dark:hover:bg-white/10 dark:border-white/10 text-text-primary transition-colors duration-150 shadow-sm"
                title="Обновить список"
              >
                <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
              </button>
            </div>
          </div>

          {/* Table Container */}
          <div className="overflow-x-auto rounded-xl border border-slate-300 dark:border-white/10 shadow-sm bg-white dark:bg-surface-elevated/30">
            <table className="w-full text-left text-xs md:text-sm border-collapse">
              <thead>
                <tr className="bg-slate-100 dark:bg-surface-elevated text-slate-700 dark:text-text-secondary uppercase text-[11px] font-bold tracking-wider border-b border-slate-300 dark:border-white/10">
                  <th className="py-3 px-4">Название и файл</th>
                  <th className="py-3 px-4">Дата создания</th>
                  <th className="py-3 px-4">Длительность</th>
                  <th className="py-3 px-4">Статус</th>
                  <th className="py-3 px-4 text-right">Действия</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-white/5">
                {isLoading ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-text-muted">
                      Загрузка истории транскрипций...
                    </td>
                  </tr>
                ) : transcriptions.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-text-muted">
                      Транскрипции не найдены.
                    </td>
                  </tr>
                ) : (
                  transcriptions.map((item) => {
                    const isExpanded = detailItem?.id === item.id;
                    return (
                      <React.Fragment key={item.id}>
                        <tr
                          className={`transition-colors duration-150 ${
                            isExpanded
                              ? "bg-indigo-50/70 dark:bg-white/[0.08]"
                              : "hover:bg-slate-50 dark:hover:bg-white/5"
                          }`}
                        >
                          <td className="py-3.5 px-4 font-semibold text-text-primary">
                            <div>{item.title || "Запись"}</div>
                            <div className="text-[11px] font-normal font-mono text-slate-500 dark:text-text-muted">
                              {item.original_filename || "—"}
                            </div>
                          </td>
                          <td className="py-3.5 px-4 text-slate-600 dark:text-text-secondary">
                            {formatDate(item.created_at)}
                          </td>
                          <td className="py-3.5 px-4 font-mono text-slate-600 dark:text-text-secondary">
                            {formatDuration(item.duration_seconds)}
                          </td>
                          <td className="py-3.5 px-4">{getStatusBadge(item.status)}</td>
                          <td className="py-3.5 px-4 text-right">
                            <div className="inline-flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => handleOpenInStudio(item.id)}
                                className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 dark:bg-indigo-500/15 dark:text-indigo-400 dark:border-indigo-500/30 dark:hover:bg-indigo-500/25 transition-colors duration-150"
                                title="Открыть в интерактивной студии"
                              >
                                Студия
                              </button>
                              <button
                                type="button"
                                onClick={() => setDetailItem(isExpanded ? null : item)}
                                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold border transition-colors duration-150 ${
                                  isExpanded
                                    ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                                    : "bg-slate-100 hover:bg-slate-200 text-slate-700 border-slate-300 dark:bg-white/5 dark:text-text-primary dark:border-white/10 dark:hover:bg-white/10"
                                }`}
                                title={isExpanded ? "Скрыть детали" : "Детали стенограммы"}
                                aria-expanded={isExpanded}
                              >
                                <span>Детали</span>
                                <ChevronDown
                                  className={`w-3.5 h-3.5 transition-transform duration-200 ${
                                    isExpanded ? "rotate-180" : ""
                                  }`}
                                />
                              </button>
                              <button
                                type="button"
                                onClick={() => setDeleteCandidate(item)}
                                className="p-1 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/15 border border-transparent hover:border-red-200 dark:hover:border-red-500/30 transition-colors duration-150"
                                title="Удалить запись"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>

                        {/* Dropdown details row attached beneath the item */}
                        {isExpanded && (
                          <tr key={`${item.id}-details`} className="bg-slate-50/90 dark:bg-surface-elevated/40 border-y border-slate-300 dark:border-white/10">
                            <td colSpan={5} className="p-4 md:p-6 animate-in fade-in slide-in-from-top-1 duration-150">
                              <div className="rounded-2xl p-5 md:p-6 bg-white dark:bg-surface border border-slate-300 dark:border-white/10 shadow-sm space-y-4">
                                <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-white/10">
                                  <div className="flex items-center gap-2">
                                    <span className="w-2.5 h-2.5 rounded-full bg-indigo-500" />
                                    <h4 className="text-sm md:text-base font-bold text-text-primary">
                                      {item.title || "Детали транскрипции"}
                                    </h4>
                                  </div>
                                  <button
                                    type="button"
                                    onClick={() => setDetailItem(null)}
                                    className="text-text-muted hover:text-text-primary p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/5 transition-colors"
                                    title="Свернуть детали"
                                  >
                                    <ChevronUp className="w-4 h-4" />
                                  </button>
                                </div>

                                <div className="p-3 rounded-xl bg-slate-100 dark:bg-surface-elevated border border-slate-200 dark:border-white/10">
                                  <audio
                                    controls
                                    src={
                                      item.audio_url ||
                                      `/api/v1/account/transcriptions/${item.id}/audio`
                                    }
                                    className="w-full h-9 rounded-lg outline-none"
                                  />
                                </div>

                                <div className="text-xs text-slate-600 dark:text-text-secondary flex flex-wrap gap-x-4 gap-y-2 p-3 rounded-xl bg-slate-50 dark:bg-surface-elevated/50 border border-slate-200 dark:border-white/10">
                                  <span>
                                    <strong className="text-text-primary">Файл:</strong> {item.original_filename || "—"}
                                  </span>
                                  <span>
                                    <strong className="text-text-primary">Дата:</strong> {formatDate(item.created_at)}
                                  </span>
                                  <span>
                                    <strong className="text-text-primary">Длительность:</strong> {formatDuration(item.duration_seconds)}
                                  </span>
                                  <span>
                                    <strong className="text-text-primary">Язык:</strong> {(item.language || "ru").toUpperCase()}
                                  </span>
                                </div>

                                <div>
                                  <span className="block text-xs font-bold text-text-primary mb-1.5">
                                    Текст расшифровки:
                                  </span>
                                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-surface-elevated border border-slate-200 dark:border-white/10 max-h-64 overflow-y-auto text-xs md:text-sm leading-relaxed whitespace-pre-wrap text-text-primary">
                                    {item.transcription_text || "Текст стенограммы отсутствует."}
                                  </div>
                                </div>

                                <div className="flex flex-wrap justify-end gap-2.5 pt-3 border-t border-slate-200 dark:border-white/10">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      if (item.transcription_text) {
                                        navigator.clipboard.writeText(item.transcription_text);
                                        showToast("Текст расшифровки скопирован!", "success");
                                      }
                                    }}
                                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-300 dark:bg-white/5 dark:hover:bg-white/10 dark:border-white/10 dark:text-text-primary transition-colors duration-150 shadow-sm"
                                  >
                                    <Copy className="w-3.5 h-3.5" />
                                    Копировать текст
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => handleOpenInStudio(item.id)}
                                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-sm hover:opacity-95 transition-opacity duration-150"
                                  >
                                    <ExternalLink className="w-3.5 h-3.5" />
                                    Открыть в Студии
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setDetailItem(null)}
                                    className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 border border-slate-300 text-slate-700 dark:bg-white/5 dark:hover:bg-white/10 dark:border-white/10 dark:text-text-secondary transition-colors duration-150"
                                  >
                                    Свернуть
                                  </button>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex flex-wrap items-center justify-between gap-3 mt-4 text-xs text-text-secondary">
            <span>
              Показано {transcriptions.length} из {pagination.total} записей (Стр. {pagination.page}{" "}
              из {pagination.total_pages})
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={pagination.page <= 1}
                onClick={() => loadTranscriptions(pagination.page - 1)}
                className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 disabled:opacity-35 border border-slate-300 dark:bg-surface-elevated dark:hover:bg-white/10 dark:border-white/10 text-text-primary transition-colors duration-150 shadow-sm"
              >
                &larr; Назад
              </button>
              <button
                type="button"
                disabled={pagination.page >= pagination.total_pages}
                onClick={() => loadTranscriptions(pagination.page + 1)}
                className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 disabled:opacity-35 border border-slate-300 dark:bg-surface-elevated dark:hover:bg-white/10 dark:border-white/10 text-text-primary transition-colors duration-150 shadow-sm"
              >
                Вперед &rarr;
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Profile Tab */}
      {accountTab === "profile" && (
        <div className="max-w-2xl">
          <div className="p-6 md:p-8 rounded-2xl bg-white dark:bg-surface-elevated border border-slate-300 dark:border-white/10 shadow-sm">
            <h3 className="text-sm md:text-base font-bold text-text-primary uppercase tracking-wider flex items-center gap-2 mb-6">
              <User className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
              Личные данные профиля
            </h3>
            <form onSubmit={handleProfileSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-text-secondary mb-1.5">
                  Имя пользователя (Логин)
                </label>
                <input
                  type="text"
                  disabled
                  value={profileData?.username || ""}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-100 dark:bg-slate-900/60 border border-slate-300 dark:border-white/5 text-sm text-slate-500 dark:text-text-muted cursor-not-allowed"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-text-secondary mb-1.5">Имя</label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="Иван"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white dark:bg-surface border border-slate-300 dark:border-white/10 text-sm text-text-primary outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 shadow-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-text-secondary mb-1.5">
                  Фамилия
                </label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Иванов"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white dark:bg-surface border border-slate-300 dark:border-white/10 text-sm text-text-primary outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 shadow-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-text-secondary mb-1.5">
                  Электронная почта
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="user@example.com"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white dark:bg-surface border border-slate-300 dark:border-white/10 text-sm text-text-primary outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 shadow-sm"
                />
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  className="w-full py-2.5 rounded-xl text-xs md:text-sm font-semibold bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-sm hover:opacity-95 transition-opacity duration-150"
                >
                  Сохранить изменения
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Security & Password Tab */}
      {accountTab === "security" && (
        <div className="max-w-2xl">
          <div className="p-6 md:p-8 rounded-2xl bg-white dark:bg-surface-elevated border border-slate-300 dark:border-white/10 shadow-sm">
            <h3 className="text-sm md:text-base font-bold text-text-primary uppercase tracking-wider flex items-center gap-2 mb-6">
              <Key className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
              Безопасность и смена пароля
            </h3>
            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-text-secondary mb-1.5">
                  Текущий пароль
                </label>
                <input
                  type="password"
                  required
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white dark:bg-surface border border-slate-300 dark:border-white/10 text-sm text-text-primary outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 shadow-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-text-secondary mb-1.5">
                  Новый пароль (минимум 8 символов)
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white dark:bg-surface border border-slate-300 dark:border-white/10 text-sm text-text-primary outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 shadow-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-text-secondary mb-1.5">
                  Подтверждение нового пароля
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white dark:bg-surface border border-slate-300 dark:border-white/10 text-sm text-text-primary outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 shadow-sm"
                />
              </div>

              <div className="pt-4">
                <button
                  type="submit"
                  className="w-full py-2.5 rounded-xl text-xs md:text-sm font-semibold bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-sm hover:opacity-95 transition-opacity duration-150"
                >
                  Обновить пароль
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteCandidate && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/80 animate-in fade-in duration-150"
          onClick={(e) => {
            if (e.target === e.currentTarget) setDeleteCandidate(null);
          }}
        >
          <div className="w-full max-w-md bg-white dark:bg-surface-elevated border border-slate-300 dark:border-white/15 rounded-2xl p-6 shadow-xl text-text-primary">
            <h3 className="text-base font-extrabold text-red-500 dark:text-red-400 mb-2">Подтверждение удаления</h3>
            <p className="text-xs md:text-sm text-slate-600 dark:text-text-secondary mb-6 leading-relaxed">
              Вы уверены, что хотите безвозвратно удалить запись «{deleteCandidate.title}» и связанный
              аудиофайл?
            </p>
            <div className="flex justify-end gap-2.5">
              <button
                type="button"
                onClick={() => setDeleteCandidate(null)}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 border border-slate-300 dark:bg-white/5 dark:hover:bg-white/10 dark:border-white/10 text-text-primary transition-colors duration-150"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={executeDelete}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-red-600 text-white hover:bg-red-700 transition-colors duration-150 shadow-sm"
              >
                Удалить безвозвратно
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
