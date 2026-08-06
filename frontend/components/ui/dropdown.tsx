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

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center justify-center focus:outline-none"
      >
        {trigger}
      </button>

      {isOpen && (
        <div
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
}: {
  children: ReactNode;
  onClick?: () => void;
  destructive?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "block w-full text-left px-4 py-2 text-sm transition-colors",
        destructive
          ? "text-error hover:bg-error/5"
          : "text-text-primary hover:bg-bg-secondary"
      )}
    >
      {children}
    </button>
  );
}

export function DropdownSeparator() {
  return <div className="border-t border-border-default my-1" />;
}
