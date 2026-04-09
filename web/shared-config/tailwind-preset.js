/** @type {import('tailwindcss').Config} */
module.exports = {
  theme: {
    screens: {
      md: '768px',
      lg: '1024px',
    },
    extend: {
      colors: {
        brand: {
          50: '#fdf8f0',
          100: '#f9eddb',
          200: '#f2d8b5',
          300: '#e9bd85',
          400: '#df9c53',
          500: '#d68332',
          600: '#c86c28',
          700: '#a65323',
          800: '#854323',
          900: '#6c381f',
          950: '#3a1b0f',
        },
        surface: {
          DEFAULT: '#ffffff',
          muted: '#f5f5f4',
          inverse: '#1c1917',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '0.5rem',
        lg: '0.75rem',
        xl: '1rem',
      },
      spacing: {
        18: '4.5rem',
        88: '22rem',
      },
    },
  },
};
