<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="logo">Admin</div>
      <el-menu
        :default-active="route.path"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <span>{{ $t('system.menu.dashboard') }}</span>
        </el-menu-item>
        <el-menu-item index="/users">
          <el-icon><User /></el-icon>
          <span>{{ $t('system.menu.userManagement') }}</span>
        </el-menu-item>
        <el-menu-item index="/roles">
          <el-icon><UserFilled /></el-icon>
          <span>{{ $t('system.menu.roleManagement') }}</span>
        </el-menu-item>
        <el-menu-item index="/logs">
          <el-icon><Document /></el-icon>
          <span>{{ $t('system.menu.logManagement') }}</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>{{ $t('system.menu.systemSettings') }}</span>
        </el-menu-item>
      </el-menu>
    </aside>

    <div class="main-area">
      <header class="top-header">
        <div class="header-left">
          <span class="page-title">{{ currentPageTitle }}</span>
        </div>
        <div class="header-right">
          <el-dropdown trigger="click" @command="handleLangChange">
            <el-button text>
              {{ $t('system.header.language') }}
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="zh-CN" :disabled="locale === 'zh-CN'">中文</el-dropdown-item>
                <el-dropdown-item command="en" :disabled="locale === 'en'">English</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <el-badge :value="3" :max="99">
            <el-button text :title="$t('system.header.notifications')">
              <el-icon><Bell /></el-icon>
            </el-button>
          </el-badge>

          <el-dropdown trigger="click" @command="handleUserCommand">
            <el-button text>
              <el-icon><UserFilled /></el-icon>
              admin
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">{{ $t('system.header.profile') }}</el-dropdown-item>
                <el-dropdown-item command="password">{{ $t('system.header.changePassword') }}</el-dropdown-item>
                <el-dropdown-item divided command="logout">{{ $t('system.login.logout') }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { setLocale } from '../lang'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Odometer, User, UserFilled, Document, Setting, Bell } from '@element-plus/icons-vue'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()

const pageTitleMap = {
  '/dashboard': () => t('system.menu.dashboard'),
  '/users': () => t('system.menu.userManagement'),
  '/roles': () => t('system.menu.roleManagement'),
  '/logs': () => t('system.menu.logManagement'),
  '/settings': () => t('system.menu.systemSettings')
}

const currentPageTitle = computed(() => {
  const fn = pageTitleMap[route.path]
  return fn ? fn() : ''
})

function handleLangChange(lang) {
  setLocale(lang)
}

async function handleUserCommand(cmd) {
  if (cmd === 'logout') {
    try {
      await ElMessageBox.confirm(t('system.login.logoutConfirm'), t('system.login.logout'), {
        confirmButtonText: t('system.common.confirm'),
        cancelButtonText: t('system.common.cancel'),
        type: 'warning'
      })
      ElMessage.success(t('system.login.logoutSuccess'))
      router.push('/login')
    } catch {
      // 用户取消
    }
  } else if (cmd === 'profile') {
    // TODO: 跳转个人中心
  } else if (cmd === 'password') {
    // TODO: 弹出修改密码对话框
  }
}
</script>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
}
.sidebar {
  width: 220px;
  background: #304156;
  overflow-y: auto;
  flex-shrink: 0;
}
.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  color: #fff;
  font-size: 20px;
  font-weight: bold;
  letter-spacing: 2px;
  background: #263445;
}
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.top-header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}
.header-left {
  display: flex;
  align-items: center;
}
.page-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  background: #f0f2f5;
}
</style>
