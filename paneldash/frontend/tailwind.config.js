/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'status-green': '#10B981',
        'status-amber': '#F59E0B',
        'status-red': '#EF4444',
      },
    },
  },
  plugins: [],
}
