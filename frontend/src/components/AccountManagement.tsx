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
    api.account
      .getProfile()
      .then((data) => {
        setProfileData(data);
        setUser(data);
        setFirstName(data.first_name || "");
        setLastName(data.last_name || "");
        setEmail(data.email || "");
      })
      .catch((err) => console.error("Error loading profile:", err));
  }, [setUser]);

  // Load transcriptions
  const loadTranscriptions = async (page = pagination.page, search = searchQuery, sort = sortBy) => {
    setIsLoading(true);
    try {
      const data = await api.account.getTranscriptions({
        page,
        limit: pagination.limit,
        search: search || undefined,
        sort_by: sort,
      });
      setTranscriptions(data.items);
      setPagination({
        page: data.page,
        limit: data.limit,
        total: data.total,
        total_pages: data.total_pages,
      });
    } catch (err) {
      console.error("Error loading transcriptions:", err);
      showToast("Ошибка при получении истории транскрипций", "error");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (accountTab === "history") {
      loadTranscriptions(1, searchQuery, sortBy);
    }
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
    <div className="bg-glass border border-white/10 dark:border-white/10 light:border-slate-200 rounded-2xl p-6 md:p-8 backdrop-blur-xl shadow-lg transition-all duration-300">
      {/* Navigation Tabs */}
      <div className="flex flex-wrap gap-2 md:gap-3 pb-4 mb-6 border-b border-white/10">
        <button
          type="button"
          onClick={() => setAccountTab("history", true)}
          className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs md:text-sm font-semibold transition-all ${
            accountTab === "history"
              ? "bg-gradient-to-r from-indigo-500 to-purple-500 text-white shadow-md shadow-indigo-500/25"
              : "bg-transparent text-text-secondary hover:text-text-primary hover:bg-white/5"
          }`}
        >
          <History className="w-4 h-4" />
          <span>История транскрипций</span>
        </button>

        <button
          type="button"
          onClick={() => setAccountTab("profile", true)}
          className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs md:text-sm font-semibold transition-all ${
            accountTab === "profile"
              ? "bg-gradient-to-r from-indigo-500 to-purple-500 text-white shadow-md shadow-indigo-500/25"
              : "bg-transparent text-text-secondary hover:text-text-primary hover:bg-white/5"
          }`}
        >
          <User className="w-4 h-4" />
          <span>Профиль</span>
        </button>

        <button
          type="button"
          onClick={() => setAccountTab("security", true)}
          className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs md:text-sm font-semibold transition-all ${
            accountTab === "security"
              ? "bg-gradient-to-r from-indigo-500 to-purple-500 text-white shadow-md shadow-indigo-500/25"
              : "bg-transparent text-text-secondary hover:text-text-primary hover:bg-white/5"
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
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  loadTranscriptions(1, e.target.value, sortBy);
                }}
                placeholder="Поиск по названию транскрипции..."
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-surface-elevated border border-white/10 text-xs md:text-sm text-text-primary outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
              />
            </div>

            <div className="flex items-center gap-2.5">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-3.5 py-2.5 rounded-xl bg-surface-elevated border border-white/10 text-xs md:text-sm text-text-primary outline-none cursor-pointer"
              >
                <option value="-created_at">Сначала новые</option>
                <option value="created_at">Сначала старые</option>
                <option value="title">По названию (А-Я)</option>
                <option value="-duration_seconds">По длительности</option>
              </select>

              <button
                type="button"
                onClick={() => loadTranscriptions(pagination.page, searchQuery, sortBy)}
                className="p-2.5 rounded-xl bg-surface-elevated hover:bg-white/10 border border-white/10 text-text-primary transition-all"
                title="Обновить список"
              >
                <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`} />
              </button>
            </div>
          </div>

          {/* Table Container */}
          <div className="overflow-x-auto rounded-xl border border-white/10">
            <table className="w-full text-left text-xs md:text-sm border-collapse">
              <thead>
                <tr className="bg-surface-elevated text-text-secondary uppercase text-[11px] font-bold tracking-wider border-b border-white/10">
                  <th className="py-3 px-4">Название и файл</th>
                  <th className="py-3 px-4">Дата создания</th>
                  <th className="py-3 px-4">Длительность</th>
                  <th className="py-3 px-4">Статус</th>
                  <th className="py-3 px-4 text-right">Действия</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
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
                  transcriptions.map((item) => (
                    <tr key={item.id} className="hover:bg-white/5 transition-colors">
                      <td className="py-3.5 px-4 font-semibold text-text-primary">
                        <div>{item.title || "Запись"}</div>
                        <div className="text-[11px] font-normal font-mono text-text-muted">
                          {item.original_filename || "—"}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-text-secondary">
                        {formatDate(item.created_at)}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-text-secondary">
                        {formatDuration(item.duration_seconds)}
                      </td>
                      <td className="py-3.5 px-4">{getStatusBadge(item.status)}</td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="inline-flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => handleOpenInStudio(item.id)}
                            className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-indigo-500/15 text-indigo-400 hover:bg-indigo-500/25 border border-indigo-500/30 transition-all"
                            title="Открыть в интерактивной студии"
                          >
                            Студия
                          </button>
                          <button
                            type="button"
                            onClick={() => setDetailItem(item)}
                            className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-white/5 text-text-primary hover:bg-white/10 border border-white/10 transition-all"
                            title="Детали стенограммы"
                          >
                            Детали
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeleteCandidate(item)}
                            className="p-1 rounded-lg text-red-400 hover:bg-red-500/15 border border-transparent hover:border-red-500/30 transition-all"
                            title="Удалить запись"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
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
                className="px-3 py-1.5 rounded-lg bg-surface-elevated hover:bg-white/10 disabled:opacity-30 border border-white/10 text-text-primary transition-all"
              >
                &larr; Назад
              </button>
              <button
                type="button"
                disabled={pagination.page >= pagination.total_pages}
                onClick={() => loadTranscriptions(pagination.page + 1)}
                className="px-3 py-1.5 rounded-lg bg-surface-elevated hover:bg-white/10 disabled:opacity-30 border border-white/10 text-text-primary transition-all"
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
          <div className="p-6 md:p-8 rounded-2xl bg-surface-elevated border border-white/10 shadow-md">
            <h3 className="text-sm md:text-base font-bold text-text-primary uppercase tracking-wider flex items-center gap-2 mb-6">
              <User className="w-5 h-5 text-indigo-400" />
              Личные данные профиля
            </h3>
            <form onSubmit={handleProfileSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                  Имя пользователя (Логин)
                </label>
                <input
                  type="text"
                  disabled
                  value={profileData?.username || ""}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-900/60 border border-white/5 text-sm text-text-muted cursor-not-allowed"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1.5">Имя</label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="Иван"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-surface border border-white/10 text-sm text-text-primary outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                  Фамилия
                </label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Иванов"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-surface border border-white/10 text-sm text-text-primary outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                  Электронная почта
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="user@example.com"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-surface border border-white/10 text-sm text-text-primary outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  className="w-full py-2.5 rounded-xl text-xs md:text-sm font-semibold bg-gradient-to-r from-indigo-500 to-purple-500 text-white shadow-md hover:opacity-95 transition-all"
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
          <div className="p-6 md:p-8 rounded-2xl bg-surface-elevated border border-white/10 shadow-md">
            <h3 className="text-sm md:text-base font-bold text-text-primary uppercase tracking-wider flex items-center gap-2 mb-6">
              <Key className="w-5 h-5 text-indigo-400" />
              Безопасность и смена пароля
            </h3>
            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                  Текущий пароль
                </label>
                <input
                  type="password"
                  required
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-surface border border-white/10 text-sm text-text-primary outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                  Новый пароль (минимум 8 символов)
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-surface border border-white/10 text-sm text-text-primary outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                  Подтверждение нового пароля
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-surface border border-white/10 text-sm text-text-primary outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                />
              </div>

              <div className="pt-4">
                <button
                  type="submit"
                  className="w-full py-2.5 rounded-xl text-xs md:text-sm font-semibold bg-gradient-to-r from-indigo-500 to-purple-500 text-white shadow-md hover:opacity-95 transition-all"
                >
                  Обновить пароль
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Detail Modal Drawer */}
      {detailItem && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={(e) => {
            if (e.target === e.currentTarget) setDetailItem(null);
          }}
        >
          <div className="w-full max-w-2xl bg-surface-elevated border border-white/15 rounded-2xl p-6 shadow-2xl text-text-primary max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-white/10">
              <h3 className="text-base font-extrabold text-text-primary truncate">
                {detailItem.title}
              </h3>
              <button
                type="button"
                onClick={() => setDetailItem(null)}
                className="text-text-muted hover:text-text-primary text-lg leading-none"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-4 pr-1">
              <div className="p-3 rounded-xl bg-surface border border-white/10">
                <audio
                  controls
                  src={
                    detailItem.audio_url ||
                    `/api/v1/account/transcriptions/${detailItem.id}/audio`
                  }
                  className="w-full h-9 rounded-lg outline-none"
                />
              </div>

              <div className="text-xs text-text-secondary flex flex-wrap gap-x-4 gap-y-1">
                <span>
                  <strong>Файл:</strong> {detailItem.original_filename || "—"}
                </span>
                <span>
                  <strong>Дата:</strong> {formatDate(detailItem.created_at)}
                </span>
                <span>
                  <strong>Длительность:</strong> {formatDuration(detailItem.duration_seconds)}
                </span>
                <span>
                  <strong>Язык:</strong> {(detailItem.language || "ru").toUpperCase()}
                </span>
              </div>

              <div>
                <span className="block text-xs font-bold text-text-primary mb-1.5">
                  Текст расшифровки:
                </span>
                <div className="p-4 rounded-xl bg-surface border border-white/10 max-h-64 overflow-y-auto text-xs md:text-sm leading-relaxed whitespace-pre-wrap text-text-primary">
                  {detailItem.transcription_text || "Текст стенограммы отсутствует."}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap justify-end gap-2.5 pt-4 mt-2 border-t border-white/10">
              <button
                type="button"
                onClick={() => {
                  if (detailItem.transcription_text) {
                    navigator.clipboard.writeText(detailItem.transcription_text);
                    showToast("Текст расшифровки скопирован!", "success");
                  }
                }}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold bg-white/5 hover:bg-white/10 border border-white/10 text-text-primary transition-all"
              >
                <Copy className="w-3.5 h-3.5" />
                Копировать текст
              </button>
              <button
                type="button"
                onClick={() => handleOpenInStudio(detailItem.id)}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold bg-gradient-to-r from-indigo-500 to-purple-500 text-white shadow-md hover:opacity-95 transition-all"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                Открыть в Студии
              </button>
              <button
                type="button"
                onClick={() => setDetailItem(null)}
                className="px-3.5 py-2 rounded-lg text-xs font-semibold bg-white/5 hover:bg-white/10 border border-white/10 text-text-secondary transition-all"
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteCandidate && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={(e) => {
            if (e.target === e.currentTarget) setDeleteCandidate(null);
          }}
        >
          <div className="w-full max-w-md bg-surface-elevated border border-white/15 rounded-2xl p-6 shadow-2xl text-text-primary">
            <h3 className="text-base font-extrabold text-red-400 mb-2">Подтверждение удаления</h3>
            <p className="text-xs md:text-sm text-text-secondary mb-6 leading-relaxed">
              Вы уверены, что хотите безвозвратно удалить запись «{deleteCandidate.title}» и связанный
              аудиофайл?
            </p>
            <div className="flex justify-end gap-2.5">
              <button
                type="button"
                onClick={() => setDeleteCandidate(null)}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-white/5 hover:bg-white/10 border border-white/10 text-text-primary transition-all"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={executeDelete}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-red-500 text-white hover:bg-red-600 transition-all shadow-md"
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
