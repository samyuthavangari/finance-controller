/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', "Inter", "system-ui", "sans-serif"],
        serif: ['"Instrument Serif"', "Georgia", "serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        ink: "var(--bg)",
        panel: "var(--panel)",
        line: "var(--line)",
        accent: "var(--accent)",
        warn: "var(--warn)",
        danger: "var(--danger)",
        muted: "var(--muted)",
        fg: "var(--text)",
      },
      boxShadow: {
        lift: "0 24px 80px -32px rgba(0,0,0,0.85)",
      },
    },
  },
  plugins: [],
};
