import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Brand
        ink: "#0F172A",

        // Semantic - Background & Surface
        bg: {
          primary: "#F8FAFC",    // slate-50 (default bg)
          secondary: "#F1F5F9",  // slate-100
          tertiary: "#E2E8F0",   // slate-200
        },

        // Semantic - Text
        text: {
          primary: "#0F172A",    // ink (primary text)
          secondary: "#475569",  // slate-600
          tertiary: "#64748B",   // slate-500
          muted: "#94A3B8",      // slate-400
          inverse: "#F8FAFC",    // light text on dark bg
        },

        // Semantic - Borders & Dividers
        border: {
          default: "#E2E8F0",    // slate-200
          dark: "#CBD5E1",       // slate-300
          light: "#F1F5F9",      // slate-100
        },

        // Semantic - Interactive
        interactive: {
          primary: "#0F172A",    // ink
          hover: "#1E293B",      // slate-800
          active: "#334155",     // slate-700
          disabled: "#E2E8F0",   // slate-200
        },

        // Status Colors - Success
        success: "#10B981",
        "success-bg": "#ECFDF5",
        "success-text": "#065F46",

        // Status Colors - Warning
        warning: "#F59E0B",
        "warning-bg": "#FFFBEB",
        "warning-text": "#92400E",

        // Status Colors - Error/Destructive
        error: "#EF4444",
        "error-bg": "#FEE2E2",
        "error-text": "#991B1B",

        // Status Colors - Info
        info: "#3B82F6",
        "info-bg": "#EFF6FF",
        "info-text": "#1E40AF",
      },

      spacing: {
        xs: "4px",
        sm: "8px",
        md: "12px",
        lg: "16px",
        xl: "24px",
        "2xl": "32px",
        "3xl": "48px",
        "4xl": "64px",
      },

      borderRadius: {
        xs: "4px",
        sm: "6px",
        md: "8px",
        lg: "12px",
        xl: "16px",
        "2xl": "24px",
      },

      fontSize: {
        "display-lg": ["36px", { lineHeight: "44px", letterSpacing: "-0.02em" }],
        "display-md": ["30px", { lineHeight: "36px", letterSpacing: "-0.02em" }],
        "heading-lg": ["24px", { lineHeight: "32px", letterSpacing: "-0.01em", fontWeight: "600" }],
        "heading-md": ["20px", { lineHeight: "28px", letterSpacing: "-0.01em", fontWeight: "600" }],
        "heading-sm": ["16px", { lineHeight: "24px", letterSpacing: "0", fontWeight: "600" }],
        "body-lg": ["16px", { lineHeight: "24px", letterSpacing: "0" }],
        "body-md": ["14px", { lineHeight: "20px", letterSpacing: "0" }],
        "body-sm": ["13px", { lineHeight: "18px", letterSpacing: "0" }],
        "label-md": ["12px", { lineHeight: "16px", letterSpacing: "0.5px", fontWeight: "500" }],
        "label-sm": ["11px", { lineHeight: "14px", letterSpacing: "0.5px", fontWeight: "500" }],
        "mono-sm": ["12px", { lineHeight: "16px", letterSpacing: "0" }],
      },

      boxShadow: {
        xs: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
        sm: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
        md: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
        lg: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
        xl: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
        "2xl": "0 25px 50px -12px rgba(0, 0, 0, 0.25)",
        "inner": "inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)",
        "none": "none",
      },

      transitionDuration: {
        fast: "100ms",
        base: "150ms",
        slow: "200ms",
        slower: "300ms",
      },

      transitionTimingFunction: {
        smooth: "cubic-bezier(0.4, 0, 0.2, 1)",
        "smooth-bounce": "cubic-bezier(0.34, 1.56, 0.64, 1)",
      },

      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
