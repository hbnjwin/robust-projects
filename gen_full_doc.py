import sqlite3
import os

db_path = os.path.join(os.environ['LOCALAPPDATA'], 'robust-manager', 'robust_manager.db')
conn = sqlite3.connect(db_path)
cur = conn.execute(
    'SELECT question_id, query, task_type, app_domain, language, weight, '
    'implicit_requirements, notes, status '
    'FROM questions ORDER BY question_id'
)
rows = cur.fetchall()
conn.close()

FOLDER_MAP = {
    'l1-001': 'wrr-table-filter-paging',
    'l1-002': 'wrr-flutter-refresh-jump',
    'l1-003': 'wrr-vue-form-stale',
    'l1-004': 'wrr-order-concurrent-dup',
    'l1-005': 'wrr-pipeline-keyerror',
    'l1-006': 'wrr-selenium-ci-flaky',
    'l1-007': 'wrr-refund-api',
    'l1-008': 'wrr-unity-nav-stuck',
    'l1-009': 'wrr-rv-duplicate-load',
    'l1-010': 'wrr-carousel-mobile-css',
    'l1-011': 'wrr-batch-import-users',
    'l1-012': 'wrr-c-gateway-memleak',
    'l1-013': 'wrr-mongo-slow-query',
    'l1-014': 'wrr-grpc-timeout-mismatch',
    'l1-015': 'wrr-fastapi-encoding',
    'l1-016': 'wrr-data-lineage-trace',
    'l1-017': 'wrr-ml-train-refactor',
    'l1-018': 'wrr-etl-schema-drift',
    'l1-019': 'wrr-kanban-drag-drop',
    'l1-020': 'wrr-infer-gpu-leak',
    'l1-021': 'wrr-rn-nav-explain',
    'l1-022': 'wrr-auto-patrol-alert',
    'l1-023': 'wrr-checkin-reward',
    'l1-024': 'wrr-order-test-coverage',
    'l1-025': 'wrr-lua-skill-dmg-bug',
    'l1-026': 'wrr-retention-calc-explain',
    'l1-027': 'wrr-java-rbac-explain',
    'l1-028': 'wrr-product-compare',
    'l1-029': 'wrr-cicd-cache-mirror',
    'l1-030': 'wrr-ab-test-routing',
}

lines = []

lines.append('# Coding L1 出题文档')
lines.append('')
lines.append('> 基于《数据需求文档 Level 1》权重表 Top30 设计，经审查调整后确保满足得分率作业要求')
lines.append('')
lines.append('## 得分率作业要求')
lines.append('')
lines.append('- **qwen 得分率 < 0.7**')
lines.append('- **claude 得分率 > qwen 得分率**')
lines.append('- **diff > 20%**（(claude得分率 - qwen得分率) / qwen得分率 > 20%）')
lines.append('')
lines.append('---')
lines.append('')
lines.append('## 题目总览')
lines.append('')
lines.append('| # | 题目ID | 任务类型 | 应用领域 | 语言 | 权重 | 项目名 |')
lines.append('|---|--------|----------|----------|------|------|--------|')

for i, r in enumerate(rows, 1):
    qid, query, tt, ad, lang, w, impl, notes, status = r
    folder = FOLDER_MAP.get(qid, qid)
    lines.append('| %d | %s | %s | %s | %s | %.1f | %s |' % (i, qid, tt, ad, lang, w, folder))

lines.append('')
lines.append('---')
lines.append('')

for i, r in enumerate(rows, 1):
    qid, query, tt, ad, lang, w, impl, notes, status = r
    folder = FOLDER_MAP.get(qid, qid)

    lines.append('## %d. %s' % (i, qid))
    lines.append('')
    lines.append('| 属性 | 值 |')
    lines.append('|------|-----|')
    lines.append('| 任务类型 | %s |' % tt)
    lines.append('| 应用领域 | %s |' % ad)
    lines.append('| 编程语言 | %s |' % lang)
    lines.append('| 权重 | %.1f |' % w)
    lines.append('| 状态 | %s |' % status)
    lines.append('| 项目名 | %s |' % folder)
    lines.append('')
    lines.append('### 题面')
    lines.append('')
    lines.append('> %s' % query)
    lines.append('')
    lines.append('### 隐式要求（Rubrics Implicit）')
    lines.append('')

    if impl:
        impl_items = [item.strip() for item in impl.split('；') if item.strip()]
        for item in impl_items:
            lines.append('- %s' % item)
    else:
        lines.append('- 无')

    lines.append('')
    lines.append('### 项目分支')
    lines.append('')
    lines.append('| 模型 | 分支名 | GitHub 仓库路径 |')
    lines.append('|------|--------|----------------|')
    lines.append('| qwen | `%s-qwen` | `https://github.com/hbnjwin/robust-projects/tree/%s-qwen` |' % (folder, folder))
    lines.append('| claude | `%s-claude` | `https://github.com/hbnjwin/robust-projects/tree/%s-claude` |' % (folder, folder))
    lines.append('')
    lines.append('---')
    lines.append('')

lines.append('## 出题设计原则')
lines.append('')
lines.append('### 1. 满足得分率作业要求的设计策略')
lines.append('')
lines.append('| 策略 | 说明 | 对应题目 |')
lines.append('|------|------|----------|')
lines.append('| 隐式要求不在题面写死 | qwen 容易只做显式部分，遗漏隐式体验要求 | 全部30题 |')
lines.append('| 题面适度模糊 | 需要模型主动澄清业务口径，qwen 倾向直接动手 | l1-004, l1-013, l1-029 |')
lines.append('| 环境兼容性要求 | 不同机型/编码/时区/版本兼容，qwen 容易只修主流程 | l1-010, l1-015, l1-023 |')
lines.append('| 并发/分布式陷阱 | 共享状态、缓存一致性、超时不一致等，qwen 容易只改表面 | l1-004, l1-014, l1-027 |')
lines.append('| 多步骤闭环 | 修复+验证+日志+测试，qwen 容易偷懒只修不改 | l1-021, l1-025, l1-026 |')
lines.append('| 复杂交互 | 拖拽、手势、动画，qwen 容易忽略边界情况 | l1-019, l1-028 |')
lines.append('')
lines.append('### 2. 对应出题指南 Bad Pattern 覆盖')
lines.append('')
lines.append('| Bad Pattern | 覆盖题目 | 设计方式 |')
lines.append('|-------------|----------|----------|')
lines.append('| 1.任务偷懒 | 全部 | 隐式要求丰富，qwen 容易只完成显式部分 |')
lines.append('| 2.不主动沟通 | l1-004, l1-013, l1-029 | 题面适度模糊，需要澄清业务口径 |')
lines.append('| 3.不主动搜github | l1-005, l1-014 | 涉及开源库版本兼容问题 |')
lines.append('| 4.环境多样性 | l1-010, l1-015, l1-023 | 机型/编码/时区兼容要求 |')
lines.append('| 5.指令follow | l1-007, l1-022, l1-030 | 多约束条件，qwen 容易遗漏 |')
lines.append('| 6.附件处理 | l1-011 | Excel 脏数据需要解析处理 |')
lines.append('| 7.只做准备不执行 | l1-024, l1-025 | 必须定位+修复+验证闭环 |')
lines.append('')
lines.append('### 3. 调整记录')
lines.append('')
lines.append('| 题目 | 原类型 | 调整后类型 | 原权重 | 新权重 | 调整原因 |')
lines.append('|------|--------|-----------|--------|--------|----------|')
lines.append('| l1-021 | code-explanation | bug-fix | 7.5 | 9.7 | 纯解释类两个模型差异小，改为修复导航bug |')
lines.append('| l1-026 | code-explanation | bug-fix | 7.0 | 7.8 | 纯解释类无法拉开差距，改为修复留存率计算bug |')
lines.append('| l1-027 | code-explanation | bug-fix | 7.0 | 9.4 | 纯解释类无法拉开差距，改为修复权限模块bug |')
lines.append('| l1-010 | bug-fix | bug-fix | 8.7 | 8.7 | 增加横屏/安卓兼容等隐式要求提升难度 |')
lines.append('| l1-011 | feature | feature | 8.6 | 8.6 | 增加Excel容错/脏数据清洗/导入报告等隐式要求 |')
lines.append('| l1-013 | bug-fix | bug-fix | 8.2 | 8.2 | 增加缓存一致性/读写分离等隐式要求 |')
lines.append('| l1-015 | bug-fix | bug-fix | 7.9 | 7.9 | 增加CORS预检/前端差异/中文文件名等隐式要求 |')
lines.append('| l1-022 | feature | feature | 7.2 | 7.2 | 增加告警风暴/智能聚合/热加载等隐式要求 |')
lines.append('| l1-023 | feature | feature | 7.2 | 7.2 | 增加防作弊/服务端时间校验等隐式要求 |')
lines.append('| l1-028 | feature | feature | 7.0 | 7.0 | 增加动态参数对齐/差异高亮/搜索/URL分享等 |')
lines.append('| l1-029 | build-release-config | bug-fix | 6.9 | 6.9 | 从"加缓存配置"改为"修缓存key+多分支冲突" |')
lines.append('| l1-030 | feature | feature | 6.8 | 6.8 | 增加按用户特征分流/统计显著性/流量染色等 |')

md = '\n'.join(lines)
out_path = r'd:\work\github\robust\docs\coding-l1-questions-full.md'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(md)

print('Written to: %s' % out_path)
print('Total questions: %d' % len(rows))
