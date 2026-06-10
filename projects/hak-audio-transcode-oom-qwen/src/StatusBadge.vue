<template>
  <el-tag :type="statusType" size="small" effect="light">
    {{ statusLabel }}
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  status: 'pending' | 'approved' | 'rejected'
}>()

const statusMap = {
  pending: { type: 'warning', label: '待审核' },
  approved: { type: 'success', label: '已通过' },
  rejected: { type: 'danger', label: '已驳回' },
} as const

const statusType = computed(() => statusMap[props.status].type)
const statusLabel = computed(() => statusMap[props.status].label)
</script>
