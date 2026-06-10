/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── Swiss Spa Premium Base ──
        surface: '#FAFAF9',
        card: '#FFFFFF',
        'card-hover': '#FAFAF9',
        'card-raised': '#FFFFFF',
        border: '#EBEAE6',
        'border-visible': '#D1CFC8',
        sidebar: '#FFFFFF',
        'sidebar-hover': '#FAFAF9',

        // ── Burnished Gold Primary ──
        primary: '#C8843C',
        'primary-hover': '#B07530',
        'primary-active': '#A06828',
        'primary-muted': '#F5F2EC',
        'primary-glow': 'rgba(200,132,60,0.08)',

        // ── Sage Green Secondary ──
        accent: '#4A9E7C',
        'accent-hover': '#3D8A6A',
        'accent-muted': 'rgba(74,158,124,0.08)',
        'accent-glow': 'rgba(74,158,124,0.10)',

        // ── Text Hierarchy ──
        'text-primary': '#1C1C1E',
        'text-secondary': '#6E6E73',
        'text-muted': '#AEAEB2',

        // ── Semantic ──
        success: '#4A9E7C',
        'success-muted': 'rgba(74,158,124,0.08)',
        warning: '#C8843C',
        'warning-muted': '#F5F2EC',
        error: '#D45A5A',
        'error-muted': 'rgba(212,90,90,0.08)',
        info: '#7A9BB5',
      },
      boxShadow: {
        soft: '0 1px 2px rgba(0,0,0,0.03)',
        card: '0 0 0 0.5px rgba(0,0,0,0.04), 0 1px 3px rgba(0,0,0,0.03)',
        raised: '0 0 0 0.5px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)',
        glow: '0 0 30px rgba(200,132,60,0.06), 0 0 60px rgba(200,132,60,0.02)',
        'glow-green': '0 0 30px rgba(74,158,124,0.06), 0 0 60px rgba(74,158,124,0.02)',
        'neon-border': '0 0 0 0.5px rgba(200,132,60,0.15), 0 0 8px rgba(200,132,60,0.04)',
      },
      fontFamily: {
        sans: ['Inter', "'Noto Sans SC'", 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', "'Noto Sans SC'", 'ui-monospace', 'monospace'],
        display: ['Inter', "'Noto Sans SC'", 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        sm: '8px',
        DEFAULT: '12px',
        lg: '16px',
        xl: '20px',
        '2xl': '24px',
      },
    },
  },
  plugins: [],
};
