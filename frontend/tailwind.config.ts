import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        moss: {
          50: "#f2f7ee",
          100: "#dfebd5",
          200: "#c2d5b0",
          300: "#a3be89",
          400: "#84a864",
          500: "#698b4d",
          600: "#4f6d3a",
          700: "#39512b",
          800: "#25391f",
          900: "#131f12"
        },
        clay: {
          100: "#f5ece2",
          300: "#d2b69a",
          500: "#9f7450",
          700: "#6f4b30",
          900: "#3f2718"
        }
      },
      boxShadow: {
        pixel: "0 0 0 2px rgba(31, 41, 55, 0.95), 6px 6px 0 rgba(15, 23, 42, 0.45)"
      }
    }
  },
  plugins: []
};

export default config;
