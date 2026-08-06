"use client";

import { ReactNode, useState } from "react";
import { cn } from "@/lib/utils";

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

  return (
    <button
      onClick={() => setActiveTab(value)}
      className={cn(
        "px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px",
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

  return <div className={cn("pt-4", className)}>{children}</div>;
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
