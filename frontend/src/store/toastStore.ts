import { create } from "zustand";
import { ToastNotification } from "../types";

interface ToastStore {
  toasts: ToastNotification[];
  addToast: (message: string, type?: ToastNotification["type"], duration?: number) => void;
  removeToast: (id: string) => void;
}

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  addToast: (message, type = "info", duration = 4000) => {
    const id = Math.random().toString(36).substring(2, 9);
    const newToast: ToastNotification = { id, message, type, duration };

    set((state) => ({ toasts: [...state.toasts, newToast] }));

    if (duration > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        }));
      }, duration);
    }
  },
  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }));
  },
}));

export const showToast = (
  message: string,
  type: ToastNotification["type"] = "info",
  duration = 4000
) => {
  useToastStore.getState().addToast(message, type, duration);
};
