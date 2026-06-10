import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { setupMockIfDev } from './api/client'

async function bootstrap() {
  // 开发环境下激活 Mock API
  await setupMockIfDev()

  const app = createApp(App)
  app.use(createPinia())
  app.use(router)
  app.mount('#app')
}

bootstrap()
