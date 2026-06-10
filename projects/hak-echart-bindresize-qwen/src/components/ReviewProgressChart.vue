<template>
  <div class="chart-container">
    <h3 class="chart-title">审核进度柱状图</h3>
    <div ref="chartRef" class="chart-wrapper"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsOption } from 'echarts'
import { useECharts } from '@/composables/useECharts'

// 模拟数据
const categories = ['待审核', '初审中', '复审中', '已通过', '已驳回']
const values = [120, 200, 150, 80, 70]

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'shadow'
    }
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true
  },
  xAxis: [
    {
      type: 'category',
      data: categories,
      axisTick: {
        alignWithLabel: true
      }
    }
  ],
  yAxis: [
    {
      type: 'value',
      name: '报告数量'
    }
  ],
  series: [
    {
      name: '审核状态',
      type: 'bar',
      barWidth: '60%',
      data: values,
      itemStyle: {
        color: (params: any) => {
          const colors = ['#E6A23C', '#409EFF', '#909399', '#67C23A', '#F56C6C']
          return colors[params.dataIndex]
        }
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
