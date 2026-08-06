"use client";

import { ReactNode, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { modalBackdrop, modalContent } from "@/lib/animations";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  closeButton?: boolean;
}

const sizes = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
  xl: "max-w-xl",
};

export function Modal({
  isOpen,
  onClose,
  title,
  children,
  size = "md",
  closeButton = true,
}: ModalProps) {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };

    if (isOpen) {
      document.addEventListener("keydown", handleEsc);
      document.body.style.overflow = "hidden";
    }

    return () => {
      document.removeEventListener("keydown", handleEsc);
      document.body.style.overflow = "";
    };
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <motion.div
            className="absolute inset-0 bg-black/50"
            onClick={onClose}
            variants={modalBackdrop}
            initial="hidden"
            animate="visible"
            exit="exit"
          />

          <motion.div
            className={cn(
              "relative bg-bg-primary rounded-lg shadow-lg p-6 w-full mx-4",
              sizes[size]
            )}
            variants={modalContent}
            initial="hidden"
            animate="visible"
            exit="exit"
          >
            {(title || closeButton) && (
              <div className="flex items-start justify-between mb-4">
                {title && (
                  <h2 className="text-lg font-semibold text-text-primary">{title}</h2>
                )}
                {closeButton && (
                  <button
                    onClick={onClose}
                    className="text-text-muted hover:text-text-primary transition-colors"
                    aria-label="Close modal"
                  >
                    <svg
                      className="w-6 h-6"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                )}
              </div>
            )}

            <div className="text-text-primary">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

export function ModalHeader({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mb-4", className)}>{children}</div>;
}

export function ModalBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mb-4", className)}>{children}</div>;
}

export function ModalFooter({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mt-6 flex gap-3 justify-end", className)}>{children}</div>;
}
