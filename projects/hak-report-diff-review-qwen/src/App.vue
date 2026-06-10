<template>
  <div id="app">
    <!-- Bug Fix #3: 固定header，高度64px -->
    <header class="app-header">
      <h1>风电报告审核系统 - Diff对比视图</h1>
      <span class="app-header-info">审核员：张工 | 项目：XX风电场</span>
    </header>

    <main class="app-main">
      <DiffViewer
        :old-content="oldReport"
        :new-content="newReport"
        old-title="V1.0 初稿"
        new-title="V2.0 修订稿"
        :header-height="64"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import DiffViewer from './components/DiffViewer.vue'

// ===== 演示数据：展示4个Bug修复 =====

// Bug Fix #1 演示：中文字符级diff
// "风机叶片桨距角" → "风机叶片浆距角" 只应标出 "桨→浆"
// Bug Fix #2 演示：表格保持完整结构
const oldReport = `
<h2>1. 风机运行参数</h2>
<p>本报告对XX风电场一期工程的3号风机进行年度运行评估。风机叶片桨距角在全年运行中保持稳定，平均值为12.5度。</p>
<table class="param-table">
<tr><th>参数名称</th><th>额定值</th><th>实测均值</th><th>偏差率</th></tr>
<tr><td>叶片桨距角</td><td>12.0°</td><td>12.5°</td><td>4.2%</td></tr>
<tr><td>发电机转速</td><td>1500 rpm</td><td>1485 rpm</td><td>1.0%</td></tr>
<tr><td>塔筒振动频率</td><td>0.35 Hz</td><td>0.33 Hz</td><td>5.7%</td></tr>
<tr><td>齿轮箱油温</td><td>65℃</td><td>62℃</td><td>4.6%</td></tr>
</table>

<h2>2. 维护建议</h2>
<p>根据监测数据，建议对3号风机叶片进行定期检修，重点关注桨距角调节系统的精度。发电机轴承温度正常，无需额外维护。</p>

<h2>3. 发电量统计</h2>
<p>本年度3号风机累计发电量为285万千瓦时，较上年度增长8.5%。其中第四季度发电量最高，达到82万千瓦时。</p>
`

const newReport = `
<h2>1. 风机运行参数</h2>
<p>本报告对XX风电场一期工程的3号风机进行年度运行评估。风机叶片浆距角在全年运行中保持稳定，平均值为13.1度。</p>
<table class="param-table">
<tr><th>参数名称</th><th>额定值</th><th>实测均值</th><th>偏差率</th></tr>
<tr><td>叶片浆距角</td><td>12.0°</td><td>13.1°</td><td>9.2%</td></tr>
<tr><td>发电机转速</td><td>1500 rpm</td><td>1490 rpm</td><td>0.7%</td></tr>
<tr><td>塔筒振动频率</td><td>0.35 Hz</td><td>0.34 Hz</td><td>2.9%</td></tr>
<tr><td>齿轮箱油温</td><td>65℃</td><td>63℃</td><td>3.1%</td></tr>
</table>

<h2>2. 维护建议</h2>
<p>根据监测数据，建议对3号风机叶片进行紧急检修，重点关注浆距角调节系统的精度和可靠性。发电机轴承温度偏高，需要增加监测频次。</p>

<h2>3. 发电量统计</h2>
<p>本年度3号风机累计发电量为291万千瓦时，较上年度增长10.2%。其中第四季度发电量最高，达到85万千瓦时。</p>
`
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  background-color: #f0f2f5;
  min-height: 100vh;
}

/* Bug Fix #3: 固定header，64px高 */
.app-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 64px;
  background: linear-gradient(135deg, #1a73e8, #0d47a1);
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  z-index: 1000;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.app-header h1 {
  font-size: 18px;
  font-weight: 600;
}

.app-header-info {
  font-size: 13px;
  opacity: 0.9;
}

.app-main {
  padding: 88px 24px 24px; /* 64px header + 24px spacing */
  max-width: 1200px;
  margin: 0 auto;
}
</style>
