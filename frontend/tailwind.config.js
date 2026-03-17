/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        shell: "rgb(var(--color-shell) / <alpha-value>)",
        panel: "rgb(var(--color-panel) / <alpha-value>)",
        panelstrong: "rgb(var(--color-panel-strong) / <alpha-value>)",
        ink: "rgb(var(--color-ink) / <alpha-value>)",
        muted: "rgb(var(--color-muted) / <alpha-value>)",
        line: "rgb(var(--color-line) / <alpha-value>)",
        teal: "rgb(var(--color-teal) / <alpha-value>)",
        amber: "rgb(var(--color-amber) / <alpha-value>)",
        coral: "rgb(var(--color-coral) / <alpha-value>)",
        sky: "rgb(var(--color-sky) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["Inter", "Aptos", "Segoe UI Variable", "system-ui", "sans-serif"],
        display: ["Inter", "Aptos Display", "Segoe UI Variable", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Cascadia Code", "Consolas", "monospace"],
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.25rem",
        "4xl": "1.5rem",
      },
      boxShadow: {
        shell: "0 8px 24px rgba(0, 0, 0, 0.3)",
        panel: "0 4px 12px rgba(0, 0, 0, 0.18)",
        glow: "0 0 24px rgba(94, 234, 212, 0.05)",
        "glow-sky": "0 0 24px rgba(129, 161, 255, 0.05)",
      },
      backdropBlur: {
        "3xl": "48px",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseline: {
          "0%, 100%": { opacity: "0.35" },
          "50%": { opacity: "0.6" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        rise: "rise 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
        pulseline: "pulseline 2.5s ease-in-out infinite",
        shimmer: "shimmer 3s ease-in-out infinite",
      },
    },
  },
  plugins: [],
}
