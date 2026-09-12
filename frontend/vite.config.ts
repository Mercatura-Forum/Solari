import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Served by the Thebes asset contract through the boundary at
//   GET /_/raw/{contract_id}/{*path}
// `base: './'` keeps every emitted URL relative to that prefix, so no contract id
// is baked into the bundle. The router is a HashRouter, so nested routes never
// depend on the base path. Chunks stay small for the asset uploader; the export
// libraries are split out and loaded only when a user exports.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: './',
  build: {
    assetsInlineLimit: 4096,
    target: 'es2022',
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        entryFileNames: 'assets/app-[hash].js',
        chunkFileNames: 'assets/chunk-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
      },
    },
  },
})
