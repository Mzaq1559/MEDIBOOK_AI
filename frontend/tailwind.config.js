/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#0058BC',
        primaryContainer: '#0070EB',
        secondary: '#006B5F',
        secondaryContainer: '#62FAE3',
        error: '#BA1A1A',
        errorContainer: '#FFDAD6',
        background: '#F8F9FF',
        surfaceContainer: '#EFF4FF',
        surfaceContainerHigh: '#E6EEFF',
        textPrimary: '#0D1C2E',
        textSecondary: '#414755',
        outline: '#C1C6D7',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        heading: ['Manrope', 'sans-serif'],
      },
      borderRadius: {
        'xl': '12px',
        '2xl': '16px',
        '3xl': '24px',
        'pill': '9999px',
      },
      boxShadow: {
        'soft-sm': '0 2px 8px 0 rgba(0, 88, 188, 0.05)',
        'soft': '0 4px 20px -2px rgba(0, 88, 188, 0.07), 0 2px 6px -1px rgba(0, 88, 188, 0.03)',
        'soft-md': '0 10px 25px -5px rgba(0, 88, 188, 0.08), 0 8px 10px -6px rgba(0, 88, 188, 0.03)',
        'soft-lg': '0 20px 35px -10px rgba(0, 88, 188, 0.1), 0 10px 15px -5px rgba(0, 88, 188, 0.04)',
        'glow-primary': '0 0 0 4px rgba(0, 88, 188, 0.15)',
        'glow-error': '0 0 0 4px rgba(186, 26, 26, 0.15)',
      },
    },
  },
  plugins: [],
}
