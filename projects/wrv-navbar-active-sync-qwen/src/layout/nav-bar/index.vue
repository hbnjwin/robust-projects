<template>
  <div class="nav-bar">
    <platform-logo />
    <div class="menu-tabs">
      <div v-for="item in menuList" :key="item.path"
        :class="['menu-item', { active: activePath === item.path }]"
        @click="handleMenuClick(item)">
        {{ item.title }}
      </div>
    </div>
    <div class="user-area">
      <t-dropdown :options="userOptions" @click="handleUserAction">
        <t-avatar>{{ username }}</t-avatar>
      </t-dropdown>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import PlatformLogo from './components/platform-logo.vue'

const router = useRouter()
const route = useRoute()
const activePath = ref('')
const username = ref('Admin')
const menuList = [
  { path: '/expert-database', title: '专家库' },
  { path: '/ai-report-review/index', title: 'AI报告审查' },
  { path: '/system/rulebase', title: '规则库' },
]
const userOptions = [{ content: '退出登录', value: 'logout' }]

onMounted(() => { activePath.value = route.path })

const handleMenuClick = (item) => {
  activePath.value = item.path
  router.push(item.path)
}
const handleUserAction = (val) => {
  if (val === 'logout') router.push('/login')
}
</script>
