import {defineConfig} from 'vite';
import {fileURLToPath} from 'node:url';

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  envDir: false,
  base: '/static/desk-ui/',
  plugins: [{name: 'html-newlines', transformIndexHtml: html => html.replace(/\r\n?/g, '\n')}],
  build: {
    outDir: fileURLToPath(new URL('../../tradingagents/web/static/desk-ui', import.meta.url)),
    emptyOutDir: true,
    license: {fileName: 'THIRD-PARTY-NOTICES.txt'},
    sourcemap: false,
    rolldownOptions: {
      onwarn(warning, defaultHandler) {
        if (warning.code === 'MODULE_LEVEL_DIRECTIVE' && warning.message.includes('"use client"')) return;
        defaultHandler(warning);
      },
    },
  },
});
