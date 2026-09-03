/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // ACEWIN brand palette — near-black carbon, neon teal/emerald glow.
        // `primary` is the signature electric teal used for nav highlights,
        // buttons and major UI; `accent` is a brighter emerald-cyan step up
        // from primary, reserved for CTAs and glow highlights; `teal` is a
        // cooler cyan companion used for secondary status badges; `gold` is
        // a warm amber kept apart from the teal family for achievement /
        // reward moments. Danger stays red — a functional/semantic color
        // for errors and destructive actions, not part of the brand triad.
        ink: "#EAF3F0",
        "ink-light": "#123B34",
        paper: "#070B10",
        surface: "#0D151C",
        primary: {
          DEFAULT: "#14D9A6",
          dark: "#0FAE86",
          light: "#0F2620",
        },
        accent: {
          DEFAULT: "#22F0C2",
          dark: "#0FC79C",
          light: "#0B241F",
        },
        danger: {
          DEFAULT: "#F2555B",
          light: "#2A1315",
        },
        border: "#16262A",
        muted: "#93A6A6",
        teal: {
          DEFAULT: "#22D3EE",
          light: "#0B2129",
        },
        gold: {
          DEFAULT: "#F5B841",
          light: "#2A2013",
        },
      },
      fontFamily: {
        display: ["Newsreader", "ui-serif", "Georgia", "serif"],
        sans: ["IBM Plex Sans", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular", "monospace"],
        // Persian/Arabic glyphs — static per-weight woff2 (no variable-font axis),
        // the safest format for Safari. Applied globally to both headings and body
        // text whenever the page is RTL; see the [dir="rtl"] overrides in index.css.
        persian: ["Vazirmatn", "Tahoma", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "8px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(18, 24, 28, 0.04), 0 1px 8px rgba(18, 24, 28, 0.03)",
        glow: "0 0 0 1px rgba(20, 217, 166, 0.18), 0 0 40px -4px rgba(34, 240, 194, 0.45), 0 20px 60px -12px rgba(20, 217, 166, 0.35)",
        "glow-gold": "0 20px 60px -15px rgba(245, 184, 65, 0.35)",
      },
      keyframes: {
        blob: {
          "0%, 100%": { transform: "translate(0px, 0px) scale(1)" },
          "33%": { transform: "translate(24px, -32px) scale(1.08)" },
          "66%": { transform: "translate(-18px, 18px) scale(0.95)" },
        },
        "float-y": {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" },
        },
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "gradient-x": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        marquee: {
          "0%": { transform: "translateX(0%)" },
          "100%": { transform: "translateX(-50%)" },
        },
        "marquee-rtl": {
          "0%": { transform: "translateX(0%)" },
          "100%": { transform: "translateX(50%)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.9)", opacity: "0.7" },
          "70%": { transform: "scale(1.6)", opacity: "0" },
          "100%": { transform: "scale(1.6)", opacity: "0" },
        },
        "spin-slow": {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        "spin-slow-reverse": {
          "0%": { transform: "rotate(360deg)" },
          "100%": { transform: "rotate(0deg)" },
        },
        "pop-in": {
          "0%": { opacity: "0", transform: "scale(0.55)" },
          "65%": { opacity: "1", transform: "scale(1.08)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
      },
      animation: {
        blob: "blob 12s ease-in-out infinite",
        "blob-delay": "blob 12s ease-in-out infinite 4s",
        "blob-delay-2": "blob 14s ease-in-out infinite 2s",
        "float-y": "float-y 5s ease-in-out infinite",
        "fade-up": "fade-up 0.7s cubic-bezier(0.16, 1, 0.3, 1) both",
        "gradient-x": "gradient-x 6s ease infinite",
        marquee: "marquee 32s linear infinite",
        "marquee-rtl": "marquee-rtl 32s linear infinite",
        shimmer: "shimmer 3s ease-in-out infinite",
        "pulse-ring": "pulse-ring 2.2s cubic-bezier(0.2, 0.6, 0.4, 1) infinite",
        "spin-slow": "spin-slow 14s linear infinite",
        "spin-slow-reverse": "spin-slow-reverse 18s linear infinite",
        "pop-in": "pop-in 0.6s cubic-bezier(0.16, 1, 0.3, 1) both",
      },
      backgroundSize: {
        "gradient-200": "200% 200%",
      },
    },
  },
  plugins: [],
};
