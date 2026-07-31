/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: 'rgb(var(--color-primary) / <alpha-value>)',
          hover: 'rgb(var(--color-primary-hover) / <alpha-value>)',
          soft: 'rgb(var(--color-primary-soft) / <alpha-value>)',
          50: 'rgb(var(--color-primary-soft) / <alpha-value>)',
          100: 'rgb(var(--color-primary-soft) / <alpha-value>)',
          200: 'rgb(var(--color-secondary) / <alpha-value>)',
          300: 'rgb(var(--color-secondary) / <alpha-value>)',
          400: 'rgb(var(--color-secondary) / <alpha-value>)',
          500: 'rgb(var(--color-primary) / <alpha-value>)',
          600: 'rgb(var(--color-primary) / <alpha-value>)',
          700: 'rgb(var(--color-primary-hover) / <alpha-value>)',
          800: 'rgb(var(--color-primary-hover) / <alpha-value>)',
          900: 'rgb(var(--color-primary-hover) / <alpha-value>)',
        },
        secondary: {
          DEFAULT: 'rgb(var(--color-bg) / <alpha-value>)',
          100: 'rgb(var(--color-bg) / <alpha-value>)',
          200: 'rgb(var(--color-border) / <alpha-value>)',
        },
        accent: 'rgb(var(--color-secondary) / <alpha-value>)',
        app: 'rgb(var(--color-bg) / <alpha-value>)',
        surface: 'rgb(var(--color-surface) / <alpha-value>)',
        navbar: 'rgb(var(--color-navbar) / <alpha-value>)',
        muted: 'rgb(var(--color-muted) / <alpha-value>)',
        appborder: 'rgb(var(--color-border) / <alpha-value>)',
        success: 'rgb(var(--color-success) / <alpha-value>)',
        warning: 'rgb(var(--color-warning) / <alpha-value>)',
        danger: 'rgb(var(--color-danger) / <alpha-value>)',
      },
      textColor: {
        app: 'rgb(var(--color-text) / <alpha-value>)',
        muted: 'rgb(var(--color-muted) / <alpha-value>)',
      },
      backgroundColor: {
        app: 'rgb(var(--color-bg) / <alpha-value>)',
        surface: 'rgb(var(--color-surface) / <alpha-value>)',
        navbar: 'rgb(var(--color-navbar) / <alpha-value>)',
      },
      borderColor: {
        app: 'rgb(var(--color-border) / <alpha-value>)',
        DEFAULT: 'rgb(var(--color-border) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
      borderRadius: {
        card: '16px',
        control: '10px',
      },
      boxShadow: {
        soft: 'var(--shadow-soft)',
        lift: 'var(--shadow-lift)',
      },
      spacing: {
        18: '4.5rem',
        22: '5.5rem',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.25s ease-out',
      },
    },
  },
  plugins: [],
};
