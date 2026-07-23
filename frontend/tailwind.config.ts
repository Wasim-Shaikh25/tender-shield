import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0F172A", // brand slate (matches checkout theme, Doc §15.5)
      },
    },
  },
  plugins: [],
};

export default config;
