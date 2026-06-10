<template>
  <div class="login-container">
    <div class="login-card">
      <h2 class="login-title">{{ $t('system.login.title') }}</h2>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="0">
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            :placeholder="$t('system.login.username')"
            prefix-icon="User"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            :placeholder="$t('system.login.password')"
            prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item prop="captcha">
          <div class="captcha-row">
            <el-input
              v-model="form.captcha"
              :placeholder="$t('system.login.captchaPlaceholder')"
              prefix-icon="Key"
            />
            <div class="captcha-img" @click="refreshCaptcha">
              {{ captchaText }}
            </div>
          </div>
        </el-form-item>
        <el-form-item>
          <div class="login-options">
            <el-checkbox v-model="form.rememberMe">{{ $t('system.login.rememberMe') }}</el-checkbox>
            <el-link type="primary" :underline="false">{{ $t('system.login.forgotPassword') }}</el-link>
          </div>
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            class="login-button"
            :loading="loading"
            @click="handleLogin"
          >
            {{ loading ? $t('system.login.loggingIn') : $t('system.login.loginButton') }}
          </el-button>
        </el-form-item>
      </el-form>
      <div class="lang-switch">
        <el-button text @click="toggleLang">
          {{ $t('system.header.language') }}: {{ currentLang }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { setLocale, getLocale } from '../../lang'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
const router = useRouter()
const formRef = ref(null)
const loading = ref(false)
const captchaText = ref('A3K9')

const form = reactive({
  username: '',
  password: '',
  captcha: '',
  rememberMe: false
})

const rules = reactive({
  username: [{ required: true, message: () => t('validation.required', { field: t('system.login.username') }), trigger: 'blur' }],
  password: [{ required: true, message: () => t('validation.required', { field: t('system.login.password') }), trigger: 'blur' }],
  captcha: [{ required: true, message: () => t('validation.required', { field: t('system.login.captcha') }), trigger: 'blur' }]
})

const currentLang = computed(() => getLocale() === 'zh-CN' ? '中文' : 'English')

function toggleLang() {
  const next = getLocale() === 'zh-CN' ? 'en' : 'zh-CN'
  setLocale(next)
}

function refreshCaptcha() {
  captchaText.value = Math.random().toString(36).substring(2, 6).toUpperCase()
}

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    // 模拟登录请求
    await new Promise(resolve => setTimeout(resolve, 1000))
    ElMessage.success(t('system.login.loginSuccess'))
    router.push('/')
  } catch {
    ElMessage.error(t('system.login.loginFailed'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-card {
  width: 420px;
  padding: 40px 36px 24px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}
.login-title {
  text-align: center;
  margin-bottom: 28px;
  font-size: 22px;
  color: #303133;
}
.captcha-row {
  display: flex;
  gap: 12px;
  width: 100%;
}
.captcha-img {
  flex-shrink: 0;
  width: 110px;
  height: 40px;
  line-height: 40px;
  text-align: center;
  background: #f0f2f5;
  border-radius: 4px;
  font-size: 18px;
  letter-spacing: 4px;
  cursor: pointer;
  user-select: none;
}
.login-options {
  display: flex;
  justify-content: space-between;
  width: 100%;
}
.login-button {
  width: 100%;
}
.lang-switch {
  text-align: center;
  margin-top: 8px;
}
</style>
