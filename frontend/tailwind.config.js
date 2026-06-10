/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F7F6F2",
        ink: "#173F35",
        ledgerRed: "#AE2B26",
      },
      fontFamily: {
        mono: ["IBM Plex Mono", "monospace"],
        display: ["Fraunces", "serif"],
      },
    },
  },
  plugins: [],
};
