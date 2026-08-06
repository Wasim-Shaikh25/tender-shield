import * as React from "react";
import { cn } from "@/lib/utils";

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "success" | "warning" | "error" | "info";
  title?: string;
}

const Alert = React.forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant = "info", title, children, ...props }, ref) => {
    const variants = {
      success: {
        bg: "bg-success-bg",
        border: "border-l-4 border-success",
        text: "text-success-text",
      },
      warning: {
        bg: "bg-warning-bg",
        border: "border-l-4 border-warning",
        text: "text-warning-text",
      },
      error: {
        bg: "bg-error-bg",
        border: "border-l-4 border-error",
        text: "text-error-text",
      },
      info: {
        bg: "bg-info-bg",
        border: "border-l-4 border-info",
        text: "text-info-text",
      },
    };

    const style = variants[variant];

    return (
      <div
        ref={ref}
        className={cn(
          "rounded-md p-4",
          style.bg,
          style.border,
          style.text,
          className
        )}
        role="alert"
        {...props}
      >
        {title && <h4 className="font-semibold mb-1">{title}</h4>}
        <div className="text-sm">{children}</div>
      </div>
    );
  }
);

Alert.displayName = "Alert";

export { Alert };
