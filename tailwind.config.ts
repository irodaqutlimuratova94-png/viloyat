import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: "#0F5132", dark: "#0B3D26", tint: "#EAF3EE" },
        ink: "#16201B", muted: "#5B6B62", line: "#DDE5E0", surface: "#F6F8F6", warn: "#9A3412",
      },
      fontFamily: { sans: ["var(--font-sans)", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
export default config;
