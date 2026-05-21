/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#5C8B67',
        'primary-hover': '#4A7053',
        'primary-active': '#3D5C43',
        accent: '#C87D53',
        surface: '#FAFAF9',
        card: '#FFFFFF',
        border: '#E7E5E0',
        sidebar: '#F5F4F0',
        'text-primary': '#1A1A18',
        'text-secondary': '#6B6B65',
        success: '#4A8C6F',
        warning: '#D4A24E',
        error: '#C85555',
      },
      boxShadow: {
        soft: '0 16px 40px rgba(26, 26, 24, 0.08)',
      },
      fontFamily: {
        sans: ['Geist', 'Noto Sans SC', 'Inter', 'ui-sans-serif', 'system-ui'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular'],
      },
    },
  },
  plugins: [],
};
