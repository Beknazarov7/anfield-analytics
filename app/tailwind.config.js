/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Liverpool FC palette — red accent, used sparingly so it's not garish.
        lfc: {
          DEFAULT: "#C8102E", // primary club red
          dark: "#7d0a1d",
          light: "#e23a52",
        },
        pitch: {
          DEFAULT: "#1f7a4d", // turf green for the shot map
          dark: "#176039",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
