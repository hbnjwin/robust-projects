<template>
  <div class="login-page">
    <t-form :data="formData" @submit="handleLogin">
      <t-form-item name="username"><t-input v-model="formData.username" placeholder="用户名" /></t-form-item>
      <t-form-item name="password"><t-input v-model="formData.password" type="password" placeholder="密码" /></t-form-item>
      <t-button type="submit" block>登录</t-button>
    </t-form>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { AUTH_CENTER, COMMON } from '@/api'
import { setOauth } from '@/utils/oauth2'
import CryptoJS from 'crypto-js'

const router = useRouter()
const formData = reactive({ username: '', password: '' })

const handleLogin = async () => {
  const pwd = CryptoJS.MD5(formData.password).toString()
  const res = await AUTH_CENTER.verifyUser({ username: formData.username, password: pwd })
  setOauth(res.token)
  COMMON.getDepartmentTree()
  COMMON.getFunctionList()
  COMMON.getUserDetail()
  router.push('/expert-database')
}
</script>
