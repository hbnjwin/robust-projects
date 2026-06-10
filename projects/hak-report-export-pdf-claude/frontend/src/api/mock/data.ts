import type { Report } from '@/types/report'

const statuses: Report['status'][] = ['draft', 'pending', 'approved', 'rejected']

const titles = [
  '2024年度风力发电机组检测报告',
  '风机叶片结构完整性评估报告',
  '海上风电场基础设施巡检报告',
  '风电机组齿轮箱振动分析报告',
  '风电场年度发电量统计报告',
  '风机塔筒焊缝无损检测报告',
  '风电场电气系统安全评估报告',
  '风机叶片雷击损伤检测报告',
  '风电场环境影响评估报告',
  '风机主轴承温度监测分析报告',
  '风电场运维成本分析报告',
  '风机变桨系统故障诊断报告',
  '海上风电场防腐蚀检测报告',
  '风电机组偏航系统检测报告',
  '风电场并网性能测试报告',
  '风机发电机绕组绝缘检测报告',
  '风电场雷电防护系统评估报告',
  '风机控制系统软件升级评估报告',
  '风电场噪声环境监测报告',
  '风机液压系统泄漏检测报告',
  '2023年度风电设备可靠性分析报告',
  '风电场鸟类生态影响评估报告',
  '风机基础沉降监测分析报告',
  '风电场集电线路绝缘检测报告',
  '风机润滑系统油品分析报告',
  '风电场安全生产检查报告',
  '风机叶片前缘腐蚀评估报告',
  '风电场气象数据分析报告',
  '风机塔筒螺栓预紧力检测报告',
  '风电场消防系统检查报告',
  '风机变流器故障分析报告',
  '风电场土地利用评估报告',
  '风机冷却系统性能评估报告',
  '风电场通信系统可靠性报告',
  '风机叶片结冰监测分析报告',
  '风电场水土保持监测报告',
  '风机联轴器对中检测报告',
  '风电场视频监控系统评估报告',
  '风机制动系统性能测试报告',
  '风电场应急预案评估报告',
  '风机传感器校准报告',
  '风电场电能质量监测报告',
  '风机振动频谱分析报告',
  '风电场防雷接地系统检测报告',
  '风机运行数据可靠性分析报告',
  '风电场升压站设备检测报告',
  '风机叶片气动性能评估报告',
  '风电场电缆绝缘老化检测报告',
  '风机齿轮箱油温异常分析报告',
  '风电场综合效能评估报告'
]

const authors = ['张工程师', '李工程师', '王工程师', '赵工程师', '刘工程师', '陈工程师']

function randomDate(start: Date, end: Date): string {
  const d = new Date(start.getTime() + Math.random() * (end.getTime() - start.getTime()))
  return d.toISOString()
}

function generateSections(reportId: string): Report['sections'] {
  const sectionTitles = ['概述', '检测方法', '检测结果', '数据分析', '结论与建议']
  return sectionTitles.map((title, i) => ({
    id: `${reportId}-s${i + 1}`,
    title,
    content: `本章节为${title}部分的详细内容。包含相关技术参数、检测数据和分析结果。`,
    order: i + 1
  }))
}

function generateAnnotations(reportId: string): Report['annotations'] {
  const comments = [
    '数据需要补充2024年的对比信息',
    '此处结论需要引用更多参考标准',
    '图表清晰度需要提升',
    '建议增加风险等级说明'
  ]
  const count = Math.floor(Math.random() * 3)
  return Array.from({ length: count }, (_, i) => ({
    id: `${reportId}-a${i + 1}`,
    sectionId: `${reportId}-s${Math.floor(Math.random() * 5) + 1}`,
    content: comments[i % comments.length],
    author: authors[Math.floor(Math.random() * authors.length)],
    createdAt: randomDate(new Date('2024-01-01'), new Date('2024-12-31'))
  }))
}

export const mockReports: Report[] = titles.map((title, i) => {
  const id = String(i + 1)
  return {
    id,
    title,
    status: statuses[i % statuses.length],
    author: authors[i % authors.length],
    reviewer: i % 3 === 0 ? null : authors[(i + 1) % authors.length],
    createdAt: randomDate(new Date('2024-01-01'), new Date('2024-06-30')),
    updatedAt: randomDate(new Date('2024-07-01'), new Date('2024-12-31')),
    sections: generateSections(id),
    annotations: generateAnnotations(id)
  }
})
