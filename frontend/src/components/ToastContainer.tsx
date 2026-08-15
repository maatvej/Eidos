import React from "react";
import { useToastStore } from "../store/toastStore";

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-6 right-6 z-[99999] flex flex-col gap-3 max-w-sm pointer-events-none"
      aria-live="polite"
      aria-atomic="true"
    >
      {toasts.map((toast) => {
        let bgClass = "bg-slate-900/90 border-slate-700 text-slate-100";
        if (toast.type === "success") {
          bgClass = "bg-emerald-950/90 border-emerald-500/50 text-emerald-100";
        } else if (toast.type === "error") {
          bgClass = "bg-red-950/90 border-red-500/50 text-red-100";
        } else if (toast.type === "warning") {
          bgClass = "bg-amber-950/90 border-amber-500/50 text-amber-100";
        } else if (toast.type === "info") {
          bgClass = "bg-indigo-950/90 border-indigo-500/50 text-indigo-100";
        }

        return (
          <div
            key={toast.id}
            role="alert"
            className={`pointer-events-auto flex items-center justify-between gap-3 px-4 py-3 rounded-xl border shadow-lg transition-opacity duration-200 animate-in fade-in slide-in-from-bottom-2 ${bgClass}`}
          >
            <span className="text-sm font-medium leading-snug">{toast.message}</span>
            <button
              type="button"
              onClick={() => removeToast(toast.id)}
              className="opacity-70 hover:opacity-100 transition-opacity text-base font-bold px-1 leading-none"
              aria-label="Закрыть уведомление"
            >
              &times;
            </button>
          </div>
        );
      })}
    </div>
  );
};
