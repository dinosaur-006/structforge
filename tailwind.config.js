/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── Studio Black Base ──
        surface: '#050508',
        card: '#0A0A10',
        'card-hover': '#0E0E16',
        'card-raised': '#111118',
        border: 'rgba(255,255,255,0.05)',
        'border-visible': 'rgba(255,255,255,0.08)',
        sidebar: '#08080D',
        'sidebar-hover': '#0E0E14',

        // ── Neon Amber Primary (timeline marker yellow) ──
        primary: '#FFB300',
        'primary-hover': '#FFC233',
        'primary-active': '#E5A100',
        'primary-muted': 'rgba(255,179,0,0.08)',
        'primary-glow': 'rgba(255,179,0,0.20)',

        // ── Waveform Green Secondary (audio meter green) ──
        accent: '#00E676',
        'accent-hover': '#33EC91',
        'accent-muted': 'rgba(0,230,118,0.08)',
        'accent-glow': 'rgba(0,230,118,0.15)',

        // ── Text Hierarchy ──
        'text-primary': '#E8E6E0',
        'text-secondary': '#8A8882',
        'text-muted': '#545250',

        // ── Semantic (muted studio tones) ──
        success: '#00E676',
        'success-muted': 'rgba(0,230,118,0.08)',
        warning: '#FFB300',
        'warning-muted': 'rgba(255,179,0,0.08)',
        error: '#FF5252',
        'error-muted': 'rgba(255,82,82,0.08)',
        info: '#448AFF',
      },
      boxShadow: {
        soft: '0 1px 2px rgba(0,0,0,0.6)',
        card: '0 0 0 0.5px rgba(255,255,255,0.04), 0 1px 3px rgba(0,0,0,0.6)',
        raised: '0 0 0 0.5px rgba(255,255,255,0.06), 0 4px 24px rgba(0,0,0,0.7)',
        glow: '0 0 30px rgba(255,179,0,0.12), 0 0 60px rgba(255,179,0,0.04)',
        'glow-green': '0 0 30px rgba(0,230,118,0.10), 0 0 60px rgba(0,230,118,0.03)',
        'neon-border': '0 0 0 0.5px rgba(255,179,0,0.3), 0 0 12px rgba(255,179,0,0.08)',
      },
      fontFamily: {
        sans: ['DM Sans', "'Noto Sans SC'", 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', "'Noto Sans SC'", 'ui-monospace', 'monospace'],
        display: ['DM Sans', "'Noto Sans SC'", 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        sm: '4px',
        DEFAULT: '6px',
        lg: '10px',
        xl: '14px',
      },
      keyframes: {
        'flicker': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.97' },
        },
        'scanline': {
          '0%': { transform: 'translateY(0)' },
          '100%': { transform: 'translateY(4px)' },
        },
        'reveal-right': {
          '0%': { transform: 'scaleX(0)', transformOrigin: 'left' },
          '100%': { transform: 'scaleX(1)', transformOrigin: 'left' },
        },
        'pulse-neon': {
          '0%, 100%': { boxShadow: '0 0 4px rgba(255,179,0,0.2)' },
          '50%': { boxShadow: '0 0 16px rgba(255,179,0,0.4)' },
        },
        'meter-bar': {
          '0%': { width: '0%' },
          '100%': { width: 'var(--meter-width)' },
        },
      },
      animation: {
        'flicker': 'flicker 4s ease-in-out infinite',
        'scanline': 'scanline 0.1s linear infinite',
        'reveal-right': 'reveal-right 0.4s ease-out',
        'pulse-neon': 'pulse-neon 2s ease-in-out infinite',
        'meter-bar': 'meter-bar 0.6s ease-out forwards',
      },
    },
  },
  plugins: [],
};
