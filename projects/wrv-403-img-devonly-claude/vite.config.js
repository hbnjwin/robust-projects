import path from 'node:path'
import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import { plugins } from './src/config'
import compressPlugin from 'vite-plugin-compression'

// https://vitejs.dev/config/
export default defineConfig(({ command }) => {
	return {
		base: './',
		envDir: './env',
		plugins: [
			vue(),
			vueJsx(),
			...plugins(),
			command === 'build' &&
				compressPlugin({
					verbose: true, // 默认即可
					disable: false, // 开启压缩(不禁用)，默认即可
					deleteOriginFile: false, // 删除源文件
					threshold: 10240, // 压缩前最小文件大小
					algorithm: 'gzip', // 压缩算法
					ext: '.gz' // 文件类型
				})
		],
		resolve: {
			alias: {
				'@': fileURLToPath(new URL('./src', import.meta.url))
			}
		},
		esbuild: {
			drop: command === 'build' ? ['console', 'debugger'] : [],
			treeShaking: true
		},
		build: {
			emptyOutDir: true,
			reportCompressedSize: false,
			chunkSizeWarningLimit: 1500,
			rollupOptions: {
				output: {
					compact: true,
					manualChunks: {
						vue: ['vue', 'vue-router', 'pinia'],
						echarts: ['echarts'],
						api: ['./src/api/index.js']
					}
				}
			}
		},
		server: {
			open: true,
			port: 3009,
			host: '0.0.0.0',
			proxy: {
				// '/pdf': {
				// 	target: 'https://mspops-verify.bluecloudatlas.cn',
				// 	changeOrigin: true,
				// 	rewrite: (path) => path.replace(/^\/pdf/, '')
				// },
				'/api': {
					changeOrigin: true,
				//	target: 'http://119.45.232.251:32729',
			   	target: 'http://127.0.0.1:8020',
					rewrite: (path) => path.replace(/^\/api/, '')
				}
			}
		},
		css: {
			preprocessorOptions: {
				less: {
					modifyVars: {
						hack: `true; @import (reference) "${path.resolve('src/style/variables.less')}";`
					},
					math: 'strict',
					javascriptEnabled: true
				}
			}
		}
	}
})
