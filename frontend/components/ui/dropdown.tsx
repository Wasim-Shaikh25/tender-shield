"use client";

import { ReactNode, useRef, useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface DropdownProps {
  trigger: ReactNode;
  children: ReactNode;
  align?: "left" | "right";
}

export function Dropdown({ trigger, children, align = "left" }: DropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (!isOpen) return;

      switch (event.key) {
        case "Escape":
          setIsOpen(false);
          break;
        case "ArrowDown": {
          event.preventDefault();
          const buttons = menuRef.current?.querySelectorAll("button");
          if (buttons && buttons.length > 0) {
            (buttons[0] as HTMLButtonElement).focus();
          }
          break;
        }
        case "ArrowUp": {
          event.preventDefault();
          const buttons = menuRef.current?.querySelectorAll("button");
          if (buttons && buttons.length > 0) {
            (buttons[buttons.length - 1] as HTMLButtonElement).focus();
          }
          break;
        }
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
        document.removeEventListener("keydown", handleKeyDown);
      };
    }
  }, [isOpen]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center justify-center focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 rounded transition-colors"
        aria-haspopup="menu"
        aria-expanded={isOpen}
      >
        {trigger}
      </button>

      {isOpen && (
        <div
          ref={menuRef}
          role="menu"
          className={cn(
            "absolute top-full mt-2 min-w-[200px] bg-bg-primary rounded-lg shadow-lg border border-border-default py-1 z-50",
            align === "right" ? "right-0" : "left-0"
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}

export function DropdownItem({
  children,
  onClick,
  destructive = false,
  disabled = false,
}: {
  children: ReactNode;
  onClick?: () => void;
  destructive?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      role="menuitem"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "block w-full text-left px-4 py-2 text-sm transition-colors focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-inset disabled:opacity-50 disabled:cursor-not-allowed",
        destructive
          ? "text-error hover:bg-error/5 disabled:hover:bg-transparent"
          : "text-text-primary hover:bg-bg-secondary disabled:hover:bg-transparent"
      )}
    >
      {children}
    </button>
  );
}

export function DropdownSeparator() {
  return <div className="border-t border-border-default my-1" />;
}
