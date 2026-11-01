/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        background: '#121525',
        surface: '#1A1E30',
        border: '#30354A',
        accent: '#725CFF',
        brand: '#725CFF',
        brandStrong: '#6D54F5',
        brandMint: '#61E7C3',
      },
    },
  },
  plugins: [],
};
