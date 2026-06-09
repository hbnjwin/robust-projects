import { defineStore } from 'pinia'

interface AppState {
  isDark: boolean
  theme: Record<string, string>
}

const CSS_VARS: Record<string, Record<string, string>> = {
  light: {
    '--el-bg-color': '#ffffff',
    '--el-text-color-primary': '#303133',
    '--el-border-color': '#dcdfe6',
    '--el-fill-color-blank': '#ffffff'
  },
  dark: {
    '--el-bg-color': '#141414',
    '--el-text-color-primary': '#e5eaf3',
    '--el-border-color': '#4c4d4f',
    '--el-fill-color-blank': '#1d1e1f'
  }
}

export const useAppStore = defineStore('app', {
  state: (): AppState => ({
    isDark: false,
    theme: {}
  }),

  actions: {
    toggleDark() {
      this.isDark = !this.isDark
      this.setCssVar()
    },

    setCssVar() {
      const vars = this.isDark ? CSS_VARS.dark : CSS_VARS.light
      // BUG: 只设置了 #app 容器的 CSS 变量
      // Element Plus 的 MessageBox、Notification、Popover 等弹窗组件
      // 是通过 Teleport 挂载到 document.body 上的
      // 这些组件不在 #app 内部，所以读不到这里设置的 CSS 变量
      const appEl = document.getElementById('app')
      if (appEl) {
        Object.entries(vars).forEach(([key, value]) => {
          appEl.style.setProperty(key, value)
        })
      }

      // BUG: 缺少对 document.documentElement (html) 或 document.body 的设置
      // 应该同时在 document.documentElement 上设置 CSS 变量
      // 或者使用 Element Plus 提供的 useDark() / useNamespace() 方案

      this.theme = vars
    },

    initTheme() {
      const saved = localStorage.getItem('isDark')
      if (saved === 'true') {
        this.isDark = true
      }
      this.setCssVar()
    }
  }
})
