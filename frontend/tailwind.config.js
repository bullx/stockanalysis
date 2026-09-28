/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "#E7E8EC",
        foam: "#FFFFFF",
        ink: {
          950: "#E7E8EC",
          900: "#F1F2F4",
          800: "#FFFFFF",
          700: "#E2E8F0",
        },
        mist: "#0F172A",
        mute: "#475569",
        line: "#E2E8F0",
        cta: "#8B5CF6",
        gold: "#B45309",
        go: "#1B6B4A",
        stop: "#A61F3A",
        warn: "#A06C12",
      },
      fontFamily: {
        sans: ["Fira Sans", "ui-sans-serif", "system-ui"],
        serif: ["Fira Sans", "ui-sans-serif", "system-ui"],
        mono: ["Fira Code", "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 18px 50px rgba(139, 92, 246, 0.28)",
        lift: "0 28px 70px rgba(40, 30, 20, 0.14)",
      },
      backgroundImage: {
        aurora:
          "radial-gradient(ellipse at 8% 0%, rgba(245, 158, 11, 0.45), transparent 42%), radial-gradient(ellipse at 92% 8%, rgba(139, 92, 246, 0.28), transparent 40%), radial-gradient(ellipse at 70% 100%, rgba(251, 191, 36, 0.2), transparent 46%)",
      },
    },
  },
  plugins: [],
};
