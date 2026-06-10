<template>
  <div class="chart-container">
    <h3 class="chart-title">发电量趋势图</h3>
    <div ref="chartRef" class="chart-wrapper"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EChartsOption } from 'echarts'
import { useECharts } from '@/composables/useECharts'

// 模拟数据
const months = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
const powerData = [820, 932, 901, 934, 1290, 1330, 1320, 1150, 980, 870, 810, 790]

const option = computed<EChartsOption>(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: '{b}<br/>{a}: {c} kWh'
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: months
  },
  yAxis: {
    type: 'value',
    name: '发电量 (kWh)'
  },
  series: [
    {
      name: '发电量',
      type: 'line',
      smooth: true,
      data: powerData,
      areaStyle: {
        opacity: 0.3
      },
      emphasis: {
        focus: 'series'
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
