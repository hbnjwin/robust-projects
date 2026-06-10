import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { copyFileSync, mkdirSync, readdirSync } from 'fs'

function copyPdfjsAssets() {
  return {
    name: 'copy-pdfjs-assets',
    buildStart() {
      const cmapSrc = resolve(__dirname, 'node_modules/pdfjs-dist/cmaps')
      const cmapDest = resolve(__dirname, 'public/cmaps')
      const fontSrc = resolve(__dirname, 'node_modules/pdfjs-dist/standard_fonts')
      const fontDest = resolve(__dirname, 'public/standard_fonts')

      for (const [src, dest] of [[cmapSrc, cmapDest], [fontSrc, fontDest]]) {
        try {
          mkdirSync(dest, { recursive: true })
          for (const file of readdirSync(src)) {
            copyFileSync(resolve(src, file), resolve(dest, file))
          }
        } catch {
          // Assets may not exist during initial install
        }
      }
    },
  }
}

export default defineConfig({
  plugins: [vue(), copyPdfjsAssets()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  optimizeDeps: {
    exclude: ['pdfjs-dist'],
  },
})
