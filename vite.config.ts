import { defineConfig, type Plugin } from 'vite';

/** Локально /sdk.js не существует: настоящий скрипт отдаёт сам Яндекс Игры. Заглушка только для dev-сервера. */
function devSdkStub(): Plugin {
  return {
    name: 'dev-sdk-stub',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/sdk.js', (_req, res) => {
        res.setHeader('Content-Type', 'application/javascript');
        res.end('/* dev: настоящий SDK подключает платформа Яндекс Игры */');
      });
    },
  };
}

export default defineConfig({
  base: './', // относительные пути: игра не привязана к адресу (п. 1.7, 1.18)
  plugins: [devSdkStub()],
  build: {
    target: 'es2015', // старые устройства (п. 1.20)
    outDir: 'dist',
    assetsInlineLimit: 0,
    sourcemap: false,
    chunkSizeWarningLimit: 2500,
  },
  server: { host: '127.0.0.1', port: 5173, strictPort: true },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true },
});
