import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  label?: string;
  help?: string;
  required?: boolean;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, label, help, required, type, ...props }, ref) => {
    return (
      <div className="space-y-1.5">
        {label && (
          <label className="block text-sm font-medium text-text-primary">
            {label}
            {required && <span className="ml-1 text-error">*</span>}
          </label>
        )}
        <input
          type={type}
          className={cn(
            "w-full rounded-md border border-border-default bg-white px-3 py-2 text-sm",
            "text-text-primary placeholder:text-text-muted",
            "transition-colors duration-base",
            "focus:border-ink focus:ring-1 focus:ring-ink focus-visible:outline-none",
            "disabled:cursor-not-allowed disabled:bg-bg-secondary disabled:text-text-muted",
            error && "border-error focus:border-error focus:ring-error",
            className
          )}
          ref={ref}
          {...props}
        />
        {error && <p className="text-sm text-error">{error}</p>}
        {help && !error && <p className="text-sm text-text-muted">{help}</p>}
      </div>
    );
  }
);

Input.displayName = "Input";

export { Input };
