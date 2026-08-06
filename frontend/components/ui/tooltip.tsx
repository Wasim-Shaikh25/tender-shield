"use client";

import { ReactNode, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  position?: "top" | "bottom" | "left" | "right";
  delay?: number;
}

const positionClasses = {
  top: "bottom-full mb-2 left-1/2 -translate-x-1/2",
  bottom: "top-full mt-2 left-1/2 -translate-x-1/2",
  left: "right-full mr-2 top-1/2 -translate-y-1/2",
  right: "left-full ml-2 top-1/2 -translate-y-1/2",
};

const arrowClasses = {
  top: "bottom-0 left-1/2 -translate-x-1/2 translate-y-full border-l-4 border-r-4 border-t-4 border-l-transparent border-r-transparent",
  bottom: "top-0 left-1/2 -translate-x-1/2 -translate-y-full border-l-4 border-r-4 border-b-4 border-l-transparent border-r-transparent",
  left: "left-0 top-1/2 -translate-y-1/2 -translate-x-full border-t-4 border-b-4 border-l-4 border-t-transparent border-b-transparent",
  right: "right-0 top-1/2 -translate-y-1/2 translate-x-full border-t-4 border-b-4 border-r-4 border-t-transparent border-b-transparent",
};

export function Tooltip({
  content,
  children,
  position = "top",
  delay = 200,
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);

  const handleMouseEnter = () => {
    timeoutRef.current = setTimeout(() => {
      setIsVisible(true);
    }, delay);
  };

  const handleMouseLeave = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setIsVisible(false);
  };

  return (
    <div
      className="relative inline-block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}

      {isVisible && (
        <div
          className={cn(
            "absolute z-50 px-2 py-1 text-xs font-medium text-white bg-text-primary rounded whitespace-nowrap pointer-events-none",
            positionClasses[position]
          )}
        >
          {content}
          <div
            className={cn(
              "absolute w-0 h-0",
              arrowClasses[position],
              "border-text-primary"
            )}
          />
        </div>
      )}
    </div>
  );
}
