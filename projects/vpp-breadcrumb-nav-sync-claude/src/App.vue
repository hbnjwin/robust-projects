<script setup lang="ts">
import { ref } from 'vue'
import { NLayout, NLayoutSider, NMenu, NLayoutContent } from 'naive-ui'

const activeMenu = ref('dashboard')
const collapsed = ref(false)

const menuOptions = [
  { label: 'Dashboard', key: 'dashboard' },
  { label: '资源管理', key: 'resource' },
  { label: '交易台', key: 'trading' },
  { label: '实时监测', key: 'monitor' },
  { label: '调控执行', key: 'control' },
  { label: '安全设置', key: 'security' },
]
</script>

<template>
  <NLayout has-sider style="height: 100vh">
    <NLayoutSider
      bordered
      :collapsed="collapsed"
      collapse-mode="width"
      :collapsed-width="64"
      :width="240"
      show-trigger
      @collapse="collapsed = true"
      @expand="collapsed = false"
    >
      <NMenu
        v-model:value="activeMenu"
        :collapsed="collapsed"
        :options="menuOptions"
      />
    </NLayoutSider>
    <NLayoutContent style="padding: 24px">
      <!-- Page content -->
      <div>{ desc } - { model }</div>
    </NLayoutContent>
  </NLayout>
</template>
