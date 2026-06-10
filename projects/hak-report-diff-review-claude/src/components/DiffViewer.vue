<script setup lang="ts">
import { reactive, computed } from 'vue'
import DiffToolbar from './DiffToolbar.vue'
import { diffReports } from '@/utils/diff'
import { useDiffNavigator } from '@/composables/useDiffNavigator'
import { useDiffAccept } from '@/composables/useDiffAccept'
import {
  DiffType,
  BlockType,
  NodeType,
  type ReportData,
  type DiffSegment,
  type DiffBlock,
  type TextDiffBlock,
  type TableDiffBlock,
  type TableCellDiff,
  type DiffChange,
} from '@/types/diff'

// ─── 风机报告示例数据 ─────────────────────────

const oldReport: ReportData = {
  title: '风电场风机运行分析报告（V1.0）',
  nodes: [
    {
      type: NodeType.Text,
      content:
        '一、概述\n本报告对XX风电场2024年度风机运行情况进行分析。风电场共安装风机48台，单机容量2.5MW，总装机容量120MW。报告期内风电场累计发电量为28560万kWh，等效利用小时数为2380小时。',
    },
    {
      type: NodeType.Text,
      content:
        '二、风机运行分析\n风机叶片桨距角控制系统运行正常，全年未发生因桨距角故障导致的停机事件。主轴承温度监测数据显示，各台风机主轴承运行温度均在正常范围内，最高温度未超过85°C。',
    },
    {
      type: NodeType.Table,
      headers: [
        { content: '参数名称' },
        { content: '设计值' },
        { content: '实测值' },
        { content: '偏差率' },
      ],
      rows: [
        [
          { content: '额定功率' },
          { content: '2500kW' },
          { content: '2480kW' },
          { content: '-0.8%' },
        ],
        [
          { content: '切入风速' },
          { content: '3.0m/s' },
          { content: '3.0m/s' },
          { content: '0%' },
        ],
        [
          { content: '额定风速' },
          { content: '11.5m/s' },
          { content: '11.2m/s' },
          { content: '-2.6%' },
        ],
        [
          { content: '切出风速' },
          { content: '25.0m/s' },
          { content: '25.0m/s' },
          { content: '0%' },
        ],
        [
          { content: '叶轮直径' },
          { content: '121m' },
          { content: '121m' },
          { content: '0%' },
        ],
      ],
    },
    {
      type: NodeType.Text,
      content:
        '三、发电量分析\n报告期内月均发电量为2380万kWh，其中7月份发电量最高达3120万kWh，2月份最低为1650万kWh。全年弃风率为3.2%，较上年度下降0.5个百分点。',
    },
    {
      type: NodeType.Text,
      content:
        '四、结论与建议\n综合以上分析，XX风电场风机整体运行状况良好，建议加强对老化部件的定期检测，确保风机运行安全。同时建议优化风机偏航控制策略，进一步提高风能利用率。',
    },
  ],
}

const newReport: ReportData = {
  title: '风电场风机运行分析报告（V2.0）',
  nodes: [
    {
      type: NodeType.Text,
      content:
        '一、概述\n本报告对XX风电场2024年度风机运行情况进行全面分析。风电场共安装风机48台，单机容量2.5MW，总装机容量120MW。报告期内风电场累计发电量为29100万kWh，等效利用小时数为2425小时。',
    },
    {
      type: NodeType.Text,
      content:
        '二、风机运行分析\n风机叶片浆距角控制系统运行稳定，全年未发生因浆距角故障导致的停机事件。主轴承温度监测数据显示，各台风机主轴承运行温度均在正常范围内，最高温度未超过82°C。',
    },
    {
      type: NodeType.Table,
      headers: [
        { content: '参数名称' },
        { content: '设计值' },
        { content: '实测值' },
        { content: '偏差率' },
      ],
      rows: [
        [
          { content: '额定功率' },
          { content: '2500kW' },
          { content: '2510kW' },
          { content: '+0.4%' },
        ],
        [
          { content: '切入风速' },
          { content: '3.0m/s' },
          { content: '3.0m/s' },
          { content: '0%' },
        ],
        [
          { content: '额定风速' },
          { content: '11.5m/s' },
          { content: '11.3m/s' },
          { content: '-1.7%' },
        ],
        [
          { content: '切出风速' },
          { content: '25.0m/s' },
          { content: '25.0m/s' },
          { content: '0%' },
        ],
        [
          { content: '叶轮直径' },
          { content: '121m' },
          { content: '121m' },
          { content: '0%' },
        ],
      ],
    },
    {
      type: NodeType.Text,
      content:
        '三、发电量分析\n报告期内月均发电量为2425万kWh，其中8月份发电量最高达3280万kWh，1月份最低为1580万kWh。全年弃风率为2.8%，较上年度下降0.9个百分点。',
    },
    {
      type: NodeType.Text,
      content:
        '四、结论与建议\n综合以上分析，XX风电场风机整体运行状态优良，建议加强对老化部件的定期检测与维护，确保风机运行安全可靠。同时建议优化风机偏航控制策略，进一步提高风能捕获效率。',
    },
  ],
}

// ─── Diff 计算 ───────────────────────────────

const diffResult = reactive(diffReports(oldReport, newReport))

const getChanges = () => diffResult.changes

const {
  currentIndex,
  currentChangeId,
  totalChanges,
  pendingCount,
  goToNext,
  goToPrev,
  goToChange,
} = useDiffNavigator(getChanges)

const {
  processedCount,
  allProcessed,
  acceptChange,
  rejectChange,
  resetChange,
  acceptAll,
  rejectAll,
} = useDiffAccept(getChanges)

// ─── 辅助函数 ────────────────────────────────

function getChange(changeId: string | undefined): DiffChange | undefined {
  if (!changeId) return undefined
  return diffResult.changes.find((c) => c.id === changeId)
}

function isProcessed(changeId: string | undefined): boolean {
  const c = getChange(changeId)
  return !!c && (c.accepted || c.rejected)
}

function isCurrent(changeId: string | undefined): boolean {
  return !!changeId && changeId === currentChangeId.value
}

function handleAccept(changeId: string) {
  acceptChange(changeId)
}

function handleReject(changeId: string) {
  rejectChange(changeId)
}

function handleReset(changeId: string) {
  resetChange(changeId)
}
</script>

<template>
  <div class="diff-viewer">
    <!-- 固定工具栏 -->
    <DiffToolbar
      :current-index="currentIndex"
      :total-changes="totalChanges"
      :pending-count="pendingCount"
      :processed-count="processedCount"
      :all-processed="allProcessed"
      @prev="goToPrev"
      @next="goToNext"
      @accept-all="acceptAll"
      @reject-all="rejectAll"
    />

    <!-- 主内容区域 -->
    <div class="diff-content">
      <!-- 列标题 -->
      <div class="diff-column-headers">
        <div class="column-header old-header">旧版报告</div>
        <div class="column-header new-header">新版报告</div>
      </div>

      <!-- Diff 块列表 -->
      <div v-for="(block, bIdx) in diffResult.blocks" :key="bIdx" class="diff-block">
        <!-- 文本块 -->
        <template v-if="block.type === BlockType.Text">
          <div
            v-for="(line, lIdx) in (block as TextDiffBlock).lines"
            :key="lIdx"
            class="diff-line-pair"
            :class="{
              'has-change': !!line.changeId,
              'is-processed': isProcessed(line.changeId),
              'is-current': isCurrent(line.changeId),
            }"
            :data-change-id="line.changeId"
          >
            <!-- 旧版行 -->
            <div class="diff-line old-side">
              <span
                v-for="(seg, sIdx) in line.oldLine"
                :key="sIdx"
                :class="{
                  'seg-equal': seg.type === DiffType.Equal,
                  'seg-removed': seg.type === DiffType.Removed && !isProcessed(line.changeId),
                  'seg-removed-done': seg.type === DiffType.Removed && isProcessed(line.changeId),
                }"
              >{{ seg.text }}</span>
            </div>

            <!-- 新版行 -->
            <div class="diff-line new-side">
              <span
                v-for="(seg, sIdx) in line.newLine"
                :key="sIdx"
                :class="{
                  'seg-equal': seg.type === DiffType.Equal,
                  'seg-added': seg.type === DiffType.Added && !isProcessed(line.changeId),
                  'seg-added-done': seg.type === DiffType.Added && isProcessed(line.changeId),
                }"
              >{{ seg.text }}</span>
            </div>

            <!-- 操作按钮 -->
            <div v-if="line.changeId && !isProcessed(line.changeId)" class="change-actions">
              <el-button size="small" type="success" @click="handleAccept(line.changeId!)">
                接受
              </el-button>
              <el-button size="small" type="danger" @click="handleReject(line.changeId!)">
                拒绝
              </el-button>
            </div>
            <div v-else-if="line.changeId && isProcessed(line.changeId)" class="change-actions processed">
              <el-tag
                :type="getChange(line.changeId)?.accepted ? 'success' : 'info'"
                size="small"
              >
                {{ getChange(line.changeId)?.accepted ? '已接受' : '已拒绝' }}
              </el-tag>
              <el-button size="small" text @click="handleReset(line.changeId!)">
                撤销
              </el-button>
            </div>
          </div>
        </template>

        <!-- 表格块 -->
        <template v-if="block.type === BlockType.Table">
          <div class="diff-table-pair">
            <!-- 旧版表格 -->
            <div class="table-side old-side">
              <table class="report-table">
                <thead>
                  <tr>
                    <th
                      v-for="(cell, cIdx) in (block as TableDiffBlock).headers"
                      :key="cIdx"
                      :colspan="cell.colspan"
                      :rowspan="cell.rowspan"
                      :class="{ 'cell-changed': !!cell.changeId && !isProcessed(cell.changeId) }"
                      :data-change-id="cell.changeId"
                    >
                      <span
                        v-for="(seg, sIdx) in cell.oldSegments"
                        :key="sIdx"
                        :class="{
                          'seg-removed': seg.type === DiffType.Removed && !isProcessed(cell.changeId),
                          'seg-removed-done': seg.type === DiffType.Removed && isProcessed(cell.changeId),
                        }"
                      >{{ seg.text }}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, rIdx) in (block as TableDiffBlock).rows" :key="rIdx">
                    <td
                      v-for="(cell, cIdx) in row"
                      :key="cIdx"
                      :colspan="cell.colspan"
                      :rowspan="cell.rowspan"
                      :class="{
                        'cell-changed': !!cell.changeId && !isProcessed(cell.changeId),
                        'is-current': isCurrent(cell.changeId),
                      }"
                      :data-change-id="cell.changeId"
                    >
                      <span
                        v-for="(seg, sIdx) in cell.oldSegments"
                        :key="sIdx"
                        :class="{
                          'seg-removed': seg.type === DiffType.Removed && !isProcessed(cell.changeId),
                          'seg-removed-done': seg.type === DiffType.Removed && isProcessed(cell.changeId),
                        }"
                      >{{ seg.text }}</span>
                      <!-- 单元格操作按钮 -->
                      <div v-if="cell.changeId && !isProcessed(cell.changeId)" class="cell-actions">
                        <el-button size="small" type="success" circle @click="handleAccept(cell.changeId!)">
                          &#10003;
                        </el-button>
                        <el-button size="small" type="danger" circle @click="handleReject(cell.changeId!)">
                          &#10005;
                        </el-button>
                      </div>
                      <div v-else-if="cell.changeId && isProcessed(cell.changeId)" class="cell-actions processed">
                        <el-tag
                          :type="getChange(cell.changeId)?.accepted ? 'success' : 'info'"
                          size="small"
                        >
                          {{ getChange(cell.changeId)?.accepted ? '已接受' : '已拒绝' }}
                        </el-tag>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- 新版表格 -->
            <div class="table-side new-side">
              <table class="report-table">
                <thead>
                  <tr>
                    <th
                      v-for="(cell, cIdx) in (block as TableDiffBlock).headers"
                      :key="cIdx"
                      :colspan="cell.colspan"
                      :rowspan="cell.rowspan"
                      :class="{ 'cell-changed': !!cell.changeId && !isProcessed(cell.changeId) }"
                    >
                      <span
                        v-for="(seg, sIdx) in cell.newSegments"
                        :key="sIdx"
                        :class="{
                          'seg-added': seg.type === DiffType.Added && !isProcessed(cell.changeId),
                          'seg-added-done': seg.type === DiffType.Added && isProcessed(cell.changeId),
                        }"
                      >{{ seg.text }}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, rIdx) in (block as TableDiffBlock).rows" :key="rIdx">
                    <td
                      v-for="(cell, cIdx) in row"
                      :key="cIdx"
                      :colspan="cell.colspan"
                      :rowspan="cell.rowspan"
                      :class="{
                        'cell-changed': !!cell.changeId && !isProcessed(cell.changeId),
                        'is-current': isCurrent(cell.changeId),
                      }"
                    >
                      <span
                        v-for="(seg, sIdx) in cell.newSegments"
                        :key="sIdx"
                        :class="{
                          'seg-added': seg.type === DiffType.Added && !isProcessed(cell.changeId),
                          'seg-added-done': seg.type === DiffType.Added && isProcessed(cell.changeId),
                        }"
                      >{{ seg.text }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.diff-viewer {
  min-height: 100vh;
  background: #f5f7fa;
}

.diff-content {
  padding: 84px 24px 40px; /* 顶部留出固定header空间 */
  max-width: 1600px;
  margin: 0 auto;
}

/* 列标题 */
.diff-column-headers {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.column-header {
  text-align: center;
  font-size: 15px;
  font-weight: 600;
  padding: 8px;
  border-radius: 6px;
}

.column-header.old-header {
  background: #fef0f0;
  color: #f56c6c;
}

.column-header.new-header {
  background: #f0f9eb;
  color: #67c23a;
}

/* Diff块 */
.diff-block {
  margin-bottom: 8px;
}

/* 文本行对 */
.diff-line-pair {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 16px;
  padding: 4px 8px;
  border-radius: 4px;
  position: relative;
  align-items: start;
}

.diff-line-pair.has-change {
  background: #fffbe6;
  border-left: 3px solid #e6a23c;
  margin: 4px 0;
  padding: 8px 12px;
}

/* 已处理的差异：高亮消失 */
.diff-line-pair.is-processed {
  background: transparent;
  border-left: 3px solid #dcdfe6;
}

/* 当前聚焦的差异 */
.diff-line-pair.is-current {
  outline: 2px solid #409eff;
  outline-offset: 2px;
}

.diff-line {
  font-size: 14px;
  line-height: 1.8;
  word-break: break-all;
  white-space: pre-wrap;
  min-height: 1.8em;
}

/* 差异高亮样式 */
.seg-removed {
  background-color: #fde2e2;
  color: #f56c6c;
  text-decoration: line-through;
  border-radius: 2px;
  padding: 0 1px;
}

.seg-added {
  background-color: #e1f3d8;
  color: #67c23a;
  font-weight: 500;
  border-radius: 2px;
  padding: 0 1px;
}

/* 已处理的差异文字：恢复普通样式，高亮消失 */
.seg-removed-done,
.seg-added-done {
  background-color: transparent;
  color: inherit;
  text-decoration: none;
  font-weight: normal;
}

/* 操作按钮 */
.change-actions {
  display: flex;
  gap: 4px;
  align-items: center;
  white-space: nowrap;
}

.change-actions.processed {
  opacity: 0.7;
}

/* 表格并排 */
.diff-table-pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin: 12px 0;
}

.table-side {
  overflow-x: auto;
}

.report-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  background: #fff;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.report-table th,
.report-table td {
  border: 1px solid #ebeef5;
  padding: 8px 12px;
  text-align: left;
  position: relative;
}

.report-table th {
  background: #f5f7fa;
  font-weight: 600;
}

/* 有差异的单元格 */
.cell-changed {
  background-color: #fffbe6 !important;
}

td.is-current,
th.is-current {
  outline: 2px solid #409eff;
  outline-offset: -2px;
}

.cell-actions {
  display: flex;
  gap: 4px;
  margin-top: 4px;
}

.cell-actions.processed {
  opacity: 0.7;
}

/* 导航聚焦动画 */
:deep(.diff-focus) {
  animation: focus-pulse 1.5s ease;
}

@keyframes focus-pulse {
  0%,
  100% {
    box-shadow: none;
  }
  50% {
    box-shadow: 0 0 0 4px rgba(64, 158, 255, 0.3);
  }
}
</style>
