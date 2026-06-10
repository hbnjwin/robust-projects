<template>
  <div class="chart-container">
    <h3 class="chart-title">故障分布饼图</h3>
    <div ref="chartRef" class="chart-wrapper"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsOption } from 'echarts'
import { useECharts } from '@/composables/useECharts'

// 模拟数据
const faultData = [
  { value: 1048, name: '机械故障' },
  { value: 735, name: '电气故障' },
  { value: 580, name: '控制系统' },
  { value: 484, name: '传感器故障' },
  { value: 300, name: '其他' }
]

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {c} ({d}%)'
  },
  legend: {
    orient: 'vertical',
    left: 'left'
  },
  series: [
    {
      name: '故障类型',
      type: 'pie',
      radius: '60%',
      data: faultData,
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      },
      label: {
        show: true,
        formatter: '{b}: {d}%'
      }
    }
  ]
}))

const { chartRef } = useECharts({ option: option.value })
</script>

<style scoped>
.chart-container {
  background: #fff;
  border-radius: 4px;
  padding: 16px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.chart-title {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.chart-wrapper {
  width: 100%;
  height: 300px;
}
</style>
