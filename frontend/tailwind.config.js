/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#0a1628',
        'navy-mid': '#0d1f3c',
        'navy-light': '#1a2f50',
        gold: '#C6A75E',
        'gold-light': '#d4b876',
        'gold-dark': '#a8893a',
        silver: '#9BA8B7',
        'silver-light': '#b8c4d0',
      },
      fontFamily: {
        display: ['"Cormorant Garamond"', 'Georgia', 'serif'],
        body: ['Montserrat', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
