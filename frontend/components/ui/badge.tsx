import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "primary" | "secondary" | "success" | "warning" | "error" | "info";
  size?: "sm" | "md";
}

const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
  ({ className, variant = "primary", size = "sm", ...props }, ref) => {
    const variants = {
      primary: "bg-ink text-white",
      secondary: "bg-bg-secondary text-text-primary",
      success: "bg-success-bg text-success-text",
      warning: "bg-warning-bg text-warning-text",
      error: "bg-error-bg text-error-text",
      info: "bg-info-bg text-info-text",
    };

    const sizes = {
      sm: "px-2.5 py-0.5 text-xs font-medium",
      md: "px-3 py-1 text-sm font-medium",
    };

    return (
      <div
        ref={ref}
        className={cn(
          "inline-flex items-center rounded-full",
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      />
    );
  }
);

Badge.displayName = "Badge";

export { Badge };
