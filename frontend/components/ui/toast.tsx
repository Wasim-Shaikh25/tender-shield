"use client";

import { ReactNode, useState, useEffect } from "react";
import { cn } from "@/lib/utils";

export type ToastType = "success" | "error" | "warning" | "info";

interface ToastProps {
  id: string;
  message: ReactNode;
  type?: ToastType;
  duration?: number;
  onClose: (id: string) => void;
}

const typeStyles = {
  success: "bg-success text-white border-success",
  error: "bg-error text-white border-error",
  warning: "bg-warning text-white border-warning",
  info: "bg-info text-white border-info",
};

const typeIcons = {
  success: "✓",
  error: "✕",
  warning: "⚠",
  info: "ℹ",
};

export function Toast({
  id,
  message,
  type = "info",
  duration = 5000,
  onClose,
}: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(() => onClose(id), duration);
    return () => clearTimeout(timer);
  }, [id, duration, onClose]);

  return (
    <div
      className={cn(
        "flex items-center gap-3 px-4 py-3 rounded-lg border animate-in fade-in slide-in-from-top-2",
        typeStyles[type]
      )}
    >
      <span className="text-lg font-bold">{typeIcons[type]}</span>
      <span className="flex-1 text-sm font-medium">{message}</span>
      <button
        onClick={() => onClose(id)}
        className="text-lg font-bold opacity-70 hover:opacity-100 transition-opacity"
        aria-label="Close notification"
      >
        ×
      </button>
    </div>
  );
}

export function ToastContainer({ toasts, onClose }: { toasts: Array<ToastProps>; onClose: (id: string) => void }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2 max-w-sm">
      {toasts.map((toast) => (
        <Toast key={toast.id} {...toast} onClose={onClose} />
      ))}
    </div>
  );
}

export function useToast() {
  const [toasts, setToasts] = useState<Array<{ id: string; message: ReactNode; type: ToastType }>>([]);

  const addToast = (message: ReactNode, type: ToastType = "info", duration = 5000) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, message, type }]);

    if (duration > 0) {
      setTimeout(() => removeToast(id), duration);
    }

    return id;
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const success = (message: ReactNode) => addToast(message, "success");
  const error = (message: ReactNode) => addToast(message, "error");
  const warning = (message: ReactNode) => addToast(message, "warning");
  const info = (message: ReactNode) => addToast(message, "info");

  return { toasts, addToast, removeToast, success, error, warning, info };
}
