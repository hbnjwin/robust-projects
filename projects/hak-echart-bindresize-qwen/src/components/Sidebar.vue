<template>
  <el-aside :width="isCollapse ? '64px' : '200px'" class="sidebar">
    <div class="logo">
      <span v-if="!isCollapse">风电审核系统</span>
      <span v-else>W</span>
    </div>

    <el-menu
      :default-active="activeMenu"
      :collapse="isCollapse"
      :unique-opened="true"
      router
    >
      <el-menu-item
        v-for="route in menuRoutes"
        :key="route.path"
        :index="route.path"
      >
        <el-icon>
          <component :is="route.meta?.icon" />
        </el-icon>
        <template #title>{{ route.meta?.title }}</template>
      </el-menu-item>
    </el-menu>

    <div class="collapse-btn" @click="toggleCollapse">
      <el-icon>
        <Expand v-if="isCollapse" />
        <Fold v-else />
      </el-icon>
    </div>
  </el-aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Expand, Fold, DataLine, Document, Monitor } from '@element-plus/icons-vue'
import router from '@/router'

const route = useRoute()

defineProps<{
  isCollapse: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle'): void
}>()

const activeMenu = computed(() => route.path)

const menuRoutes = computed(() => {
  return router.options.routes.filter(r => r.path !== '/' && r.meta?.title)
})

const toggleCollapse = () => {
  emit('toggle')
}
</script>

<style scoped>
.sidebar {
  background-color: #304156;
  transition: width 0.3s;
  overflow: hidden;
}

.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  font-size: 20px;
  font-weight: bold;
  color: #fff;
  background-color: #2b3a4b;
}

.el-menu {
  border-right: none;
  background-color: #304156;
}

:deep(.el-menu-item) {
  color: #bfcbd9;
}

:deep(.el-menu-item:hover),
:deep(.el-menu-item.is-active) {
  background-color: #263445 !important;
  color: #409eff !important;
}

.collapse-btn {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  cursor: pointer;
  color: #bfcbd9;
  font-size: 20px;
  padding: 10px;
  transition: color 0.3s;
}

.collapse-btn:hover {
  color: #409eff;
}
</style>
