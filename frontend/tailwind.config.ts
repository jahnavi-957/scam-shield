import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: ['class'],
  content: [
    './src/**/*.{ts,tsx}',
    './index.html',
  ],
  theme: {
    container: {
      center: true,
      padding: {
        DEFAULT: '1.25rem',
        sm: '1.5rem',
        lg: '2rem',
        xl: '2.5rem',
      },
    },
    extend: {
      colors: {
        bg: {
          DEFAULT: '#fbfaf7',
          elevated: '#ffffff',
          soft: '#f4f2ec',
          hover: '#f0ede5',
        },
        ink: {
          DEFAULT: '#1c1b19',
          soft: '#4a4741',
          faint: '#8a857b',
        },
        line: {
          DEFAULT: '#e6e3da',
          soft: '#f0ede5',
        },
        accent: {
          DEFAULT: '#3b3f8c',
          soft: '#eef0fb',
          ink: '#2a2e6e',
        },
        danger: {
          DEFAULT: '#b3402f',
          soft: '#f7eae6',
          ink: '#7c2a1d',
        },
        safe: {
          DEFAULT: '#2f7d5a',
          soft: '#e8f1ec',
          ink: '#1f5439',
        },
        neutral: {
          DEFAULT: '#6b675e',
          soft: '#eceae3',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
        mono: [
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Monaco',
          'Consolas',
          'monospace',
        ],
      },
      fontSize: {
        xs: ['0.75rem', { lineHeight: '1.4' }],
        sm: ['0.875rem', { lineHeight: '1.5' }],
        base: ['1rem', { lineHeight: '1.6' }],
        lg: ['1.125rem', { lineHeight: '1.55' }],
        xl: ['1.375rem', { lineHeight: '1.4' }],
        '2xl': ['1.75rem', { lineHeight: '1.35' }],
        '3xl': ['2.25rem', { lineHeight: '1.3' }],
        '4xl': ['3rem', { lineHeight: '1.25' }],
        '5xl': ['3.75rem', { lineHeight: '1.2' }],
      },
      fontWeight: {
        regular: '400',
        medium: '500',
        semibold: '600',
        bold: '700',
      },
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
        '26': '6.5rem',
        '30': '7.5rem',
        '34': '8.5rem',
        '38': '9.5rem',
      },
      borderRadius: {
        sm: '6px',
        md: '10px',
        lg: '14px',
        xl: '20px',
        '2xl': '28px',
      },
      boxShadow: {
        sm: '0 1px 2px rgba(28, 27, 25, 0.04)',
        md: '0 4px 12px rgba(28, 27, 25, 0.06)',
        lg: '0 12px 32px rgba(28, 27, 25, 0.08)',
      },
      animation: {
        'fade-in': 'fadeIn 260ms var(--ease) both',
        'slide-up': 'slideUp 260ms var(--ease) both',
        'pulse-soft': 'pulseSoft 2s var(--ease) infinite',
        'marquee-slow': 'marqueeSlow 28s linear infinite',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.45' },
        },
        marqueeSlow: {
          from: { transform: 'translateX(0)' },
          to: { transform: 'translateX(-50%)' },
        },
      },
    },
  },
  plugins: [],
};

export default config;