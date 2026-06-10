<template>
  <el-container class="app-container">
    <Sidebar :is-collapse="isCollapse" @toggle="toggleSidebar" />

    <el-container class="main-container">
      <el-header class="app-header">
        <div class="header-content">
          <h2>风电报告审核系统</h2>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component
              :is="Component"
              v-if="$route.meta.keepAlive"
              :key="$route.path"
            />
          </keep-alive>
          <component
            :is="Component"
            v-if="!$route.meta.keepAlive"
            :key="$route.path"
          />
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import Sidebar from '@/components/Sidebar.vue'

const isCollapse = ref(false)

const toggleSidebar = () => {
  isCollapse.value = !isCollapse.value
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.app-container {
  height: 100%;
}

.main-container {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.app-header {
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  display: flex;
  align-items: center;
  padding: 0 20px;
}

.header-content h2 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

.app-main {
  background-color: #f0f2f5;
  overflow-y: auto;
}
</style>
