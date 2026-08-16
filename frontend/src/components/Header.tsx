import React from "react";
import { Mic, User, LogOut, Sun, Moon, Sparkles } from "lucide-react";
import { useAppStore } from "../store/useAppStore";

export const Header: React.FC = () => {
  const { theme, toggleTheme, user, currentView, accountTab, jobId, navigate } = useAppStore();

  const isAccount = currentView === "account";

  return (
    <header className="flex flex-wrap items-center justify-between gap-4 py-4 px-6 mb-6 bg-white/95 dark:bg-slate-900/80 border border-slate-300 dark:border-white/10 rounded-2xl shadow-sm">
      {/* Brand Section */}
      <a
        href="/"
        onClick={(e) => {
          e.preventDefault();
          navigate("/", { resetState: true });
        }}
        className="flex items-center gap-4 text-inherit no-underline group cursor-pointer focus:outline-none"
        aria-label="Eidos Voice Intelligence — Главная страница"
      >
        <div className="w-11 h-11 rounded-xl bg-indigo-50 dark:bg-indigo-500/15 border border-indigo-200 dark:border-indigo-500/30 flex items-center justify-center text-indigo-600 dark:text-indigo-400 group-hover:bg-indigo-100 dark:group-hover:bg-indigo-500/25 transition-colors shadow-sm">
          <Mic className="w-6 h-6" />
        </div>
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-lg md:text-xl font-extrabold tracking-tight text-text-primary">
              Eidos Voice Intelligence
            </h1>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-50 text-indigo-600 border border-indigo-200 dark:bg-indigo-500/15 dark:text-indigo-400 dark:border-indigo-500/30">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              v1.0 Ready
            </span>
          </div>
          <p className="text-xs md:text-sm text-text-muted mt-0.5">
            Интеллектуальная транскрипция, диаризация спикеров и исполнительная аналитика встреч
          </p>
        </div>
      </a>

      {/* Header Actions */}
      <div className="flex items-center gap-3">
        {/* View Switcher Toggle */}
        <button
          type="button"
          onClick={() => {
            if (isAccount) {
              navigate(jobId ? `/jobs/${jobId}` : "/");
            } else {
              navigate(`/account/${accountTab || "history"}`);
            }
          }}
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-semibold border transition-colors duration-150 bg-indigo-50 hover:bg-indigo-100 border-indigo-200 hover:border-indigo-300 text-indigo-700 dark:bg-indigo-500/15 dark:border-indigo-500/30 dark:text-indigo-400 dark:hover:bg-indigo-500/25 dark:hover:border-indigo-500/50"
          aria-pressed={isAccount}
          title={isAccount ? "Вернуться в Студию" : "Переключить в Личный кабинет"}
        >
          {isAccount ? (
            <>
              <Sparkles className="w-4 h-4" />
              <span>Студия</span>
            </>
          ) : (
            <>
              <User className="w-4 h-4" />
              <span>Личный кабинет</span>
            </>
          )}
        </button>

        {/* User Profile Widget */}
        <div className="inline-flex items-center gap-2.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 dark:bg-white/5 border border-slate-300 dark:border-white/10 text-text-primary">
          <div className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-600 dark:bg-indigo-500/20 dark:text-indigo-400 flex items-center justify-center">
            <User className="w-3.5 h-3.5" />
          </div>
          <span className="max-w-[140px] truncate font-medium">
            {user ? user.full_name || user.username || user.email : "Загрузка..."}
          </span>
          <a
            href="/accounts/logout/"
            className="inline-flex items-center gap-1 text-slate-500 hover:text-red-500 dark:text-slate-400 dark:hover:text-red-400 transition-colors ml-1"
            title="Выйти из учетной записи"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Выход</span>
          </a>
        </div>

        {/* Theme Toggle Button */}
        <button
          type="button"
          onClick={toggleTheme}
          className="w-9 h-9 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 hover:bg-slate-200 dark:bg-white/5 dark:hover:bg-white/10 text-text-primary flex items-center justify-center transition-colors duration-150"
          aria-label={theme === "dark" ? "Переключить на светлую тему" : "Переключить на тёмную тему"}
          title={theme === "dark" ? "Переключить на светлую тему" : "Переключить на тёмную тему"}
        >
          {theme === "dark" ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-indigo-400" />
          )}
        </button>
      </div>
    </header>
  );
};
