/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#1a1a1a",
        secondary: "#252525",
        panel: "#2d2d2d",
        hover: "#353535",
        active: "#404040",
        accent: "#6c5ce7",
        "accent-hover": "#7d6ff0",
        border: "#3d3d3d",
        muted: "#999999",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
