"use client";

import { ReactNode, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { modalBackdrop, modalContent } from "@/lib/animations";

const FOCUSABLE_ELEMENTS = [
  "button",
  "input",
  "select",
  "textarea",
  "[href]",
  "[tabindex]:not([tabindex=\\-1])",
].join(",");

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
  const contentRef = useRef<HTMLDivElement>(null);
  const previousActiveElement = useRef<Element | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    // Save the previously focused element
    previousActiveElement.current = document.activeElement;

    // Focus management
    const focusFirstElement = () => {
      if (!contentRef.current) return;
      const focusableElements = contentRef.current.querySelectorAll(FOCUSABLE_ELEMENTS);
      if (focusableElements.length > 0) {
        (focusableElements[0] as HTMLElement).focus();
      }
    };

    // Focus trap
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }

      if (e.key === "Tab" && contentRef.current) {
        const focusableElements = contentRef.current.querySelectorAll(FOCUSABLE_ELEMENTS);
        if (focusableElements.length === 0) return;

        const firstElement = focusableElements[0] as HTMLElement;
        const lastElement = focusableElements[focusableElements.length - 1] as HTMLElement;
        const activeElement = document.activeElement;

        if (e.shiftKey) {
          if (activeElement === firstElement) {
            lastElement.focus();
            e.preventDefault();
          }
        } else {
          if (activeElement === lastElement) {
            firstElement.focus();
            e.preventDefault();
          }
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";

    // Use setTimeout to ensure DOM is ready
    setTimeout(focusFirstElement, 0);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
      // Restore focus to the previously focused element
      if (previousActiveElement.current instanceof HTMLElement) {
        previousActiveElement.current.focus();
      }
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
            ref={contentRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={title ? "modal-title" : undefined}
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
                  <h2 id="modal-title" className="text-lg font-semibold text-text-primary">{title}</h2>
                )}
                {closeButton && (
                  <button
                    onClick={onClose}
                    type="button"
                    className="text-text-muted hover:text-text-primary transition-colors rounded focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2"
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
