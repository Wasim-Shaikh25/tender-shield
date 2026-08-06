"use client";

import { ReactNode, useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { fadeIn } from "@/lib/animations";

interface TabsProps {
  defaultTab: string;
  children: ReactNode;
  className?: string;
}

interface TabProps {
  id: string;
  label: string;
  children: ReactNode;
}

interface TabsContextType {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

const TabsContext = require("react").createContext<TabsContextType | null>(null);

export function Tabs({ defaultTab, children, className }: TabsProps) {
  const [activeTab, setActiveTab] = useState(defaultTab);

  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab }}>
      <div className={className}>
        {children}
      </div>
    </TabsContext.Provider>
  );
}

export function TabList({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      role="tablist"
      className={cn(
        "flex border-b border-border-default gap-0",
        className
      )}
    >
      {children}
    </div>
  );
}

export function TabTrigger({
  value,
  children,
  className,
}: {
  value: string;
  children: ReactNode;
  className?: string;
}) {
  const context = require("react").useContext(TabsContext);

  if (!context) {
    throw new Error("TabTrigger must be used within Tabs");
  }

  const { activeTab, setActiveTab } = context;
  const isActive = activeTab === value;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Arrow key navigation for tabs
    if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      // Find previous tab (this is a simplified version)
      const buttons = (e.currentTarget.parentElement?.querySelectorAll("button") || []) as NodeListOf<HTMLButtonElement>;
      const currentIndex = Array.from(buttons).indexOf(e.currentTarget as HTMLButtonElement);
      if (currentIndex > 0) {
        buttons[currentIndex - 1].focus();
        buttons[currentIndex - 1].click();
      }
    } else if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      // Find next tab
      const buttons = (e.currentTarget.parentElement?.querySelectorAll("button") || []) as NodeListOf<HTMLButtonElement>;
      const currentIndex = Array.from(buttons).indexOf(e.currentTarget as HTMLButtonElement);
      if (currentIndex < buttons.length - 1) {
        buttons[currentIndex + 1].focus();
        buttons[currentIndex + 1].click();
      }
    }
  };

  return (
    <button
      id={`tab-trigger-${value}`}
      role="tab"
      aria-selected={isActive}
      aria-controls={`tab-panel-${value}`}
      onClick={() => setActiveTab(value)}
      onKeyDown={handleKeyDown}
      className={cn(
        "px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 rounded-t",
        isActive
          ? "border-ink text-ink"
          : "border-transparent text-text-muted hover:text-text-primary",
        className
      )}
    >
      {children}
    </button>
  );
}

export function TabContent({
  value,
  children,
  className,
}: {
  value: string;
  children: ReactNode;
  className?: string;
}) {
  const context = require("react").useContext(TabsContext);

  if (!context) {
    throw new Error("TabContent must be used within Tabs");
  }

  const { activeTab } = context;

  if (activeTab !== value) return null;

  return (
    <motion.div
      id={`tab-panel-${value}`}
      role="tabpanel"
      aria-labelledby={`tab-trigger-${value}`}
      className={cn("pt-4", className)}
      variants={fadeIn}
      initial="hidden"
      animate="visible"
      exit="exit"
    >
      {children}
    </motion.div>
  );
}

export function Tab({ id, label, children }: TabProps) {
  const context = require("react").useContext(TabsContext);

  if (!context) {
    throw new Error("Tab must be used within Tabs");
  }

  const { activeTab } = context;
  const isActive = activeTab === id;

  return isActive ? <div>{children}</div> : null;
}
