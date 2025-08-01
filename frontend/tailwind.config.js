/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Couleurs Revolt personnalisées
        revolt: {
          background: '#191919',
          foreground: '#242424',
          primary: '#FD6671',
          secondary: '#F8F8F2',
          accent: '#FF7800',
          success: '#65E572',
          warning: '#FAD247',
          error: '#ED4245',
          text: '#F2F3F5',
          'text-muted': '#96989D',
        },
        // Couleurs Discord-like pour la compatibilité
        discord: {
          'blurple': '#5865F2',
          'green': '#57F287',
          'yellow': '#FEE75C',
          'fuschia': '#EB459E',
          'red': '#ED4245',
          'white': '#FFFFFF',
          'black': '#000000',
          'dark-but-not-black': '#2C2F33',
          'not-quite-black': '#23272A',
          'actually-black': '#000000',
          'dark-grey': '#99AAB5',
          'grey': '#7289DA',
          'light-grey': '#BCC0C0',
        }
      },
      fontFamily: {
        'sans': ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'bounce-gentle': 'bounceGentle 2s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        bounceGentle: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5px)' },
        },
      },
      boxShadow: {
        'revolt': '0 8px 16px rgba(0, 0, 0, 0.24)',
        'revolt-lg': '0 16px 32px rgba(0, 0, 0, 0.32)',
      },
      borderRadius: {
        'revolt': '8px',
      }
    },
  },
  plugins: [],
  darkMode: 'class',
}