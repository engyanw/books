/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef6ff", 100: "#d9eaff", 200: "#b6d4ff", 300: "#84b6ff",
          400: "#4f8dff", 500: "#2f6bff", 600: "#1e54e6", 700: "#1a44b8",
          800: "#1a3a93", 900: "#1c3576",
        },
        ink: { 900: "#0f172a", 700: "#334155", 500: "#64748b", 300: "#cbd5e1" },
      },
      fontFamily: {
        sans: ['"PingFang SC"', '"Microsoft YaHei"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
