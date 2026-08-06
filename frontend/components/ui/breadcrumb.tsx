import Link from "next/link";
import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface BreadcrumbProps {
  children: ReactNode;
  className?: string;
}

interface BreadcrumbItemProps {
  href?: string;
  children: ReactNode;
  isActive?: boolean;
}

export function Breadcrumb({ children, className }: BreadcrumbProps) {
  return (
    <nav
      className={cn("flex items-center gap-2 text-sm", className)}
      aria-label="Breadcrumb"
    >
      {children}
    </nav>
  );
}

export function BreadcrumbItem({
  href,
  children,
  isActive = false,
}: BreadcrumbItemProps) {
  return (
    <div className="flex items-center gap-2">
      {href ? (
        <Link
          href={href}
          className="text-ink hover:underline transition-colors"
        >
          {children}
        </Link>
      ) : (
        <span className={isActive ? "text-text-primary font-medium" : "text-text-muted"}>
          {children}
        </span>
      )}
      {!isActive && (
        <span className="text-text-muted">/</span>
      )}
    </div>
  );
}
