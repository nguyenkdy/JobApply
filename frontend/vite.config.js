import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(['account', 'job', 'application'].map((service, i) => [`/api/${service}`, {
      target: `http://127.0.0.1:${8001 + i}`,
      changeOrigin: true,
      rewrite: path => path.replace(`/api/${service}`, '')
    }]))
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test-setup.js',
    include: ['src/**/*.test.{js,jsx}']
  }
});
