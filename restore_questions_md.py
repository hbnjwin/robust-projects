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

lines = []
lines.append('# Coding L1 题目清单 (30道)')
lines.append('')
lines.append('> 基于权重表 Top30 设计，按权重降序排列')
lines.append('')
lines.append('| # | 题目ID | 任务类型 | 应用领域 | 语言 | 权重 | 题面 |')
lines.append('|---|--------|----------|----------|------|------|------|')
for r in rows:
    qid, query, tt, ad, lang, w, impl, notes, status = r
    lines.append('| %s | %s | %s | %s | %s | %.1f | %s |' % (
        qid.replace('l1-',''), qid, tt, ad, lang, w, query.replace('|','\\|')[:80]
    ))

lines.append('')
lines.append('---')
lines.append('')

for r in rows:
    qid, query, tt, ad, lang, w, impl, notes, status = r
    lines.append('## %s' % qid)
    lines.append('')
    lines.append('- **任务类型**: %s' % tt)
    lines.append('- **应用领域**: %s' % ad)
    lines.append('- **编程语言**: %s' % lang)
    lines.append('- **权重**: %.1f' % w)
    lines.append('- **状态**: %s' % status)
    lines.append('')
    lines.append('### 题面')
    lines.append('')
    lines.append(query)
    lines.append('')
    lines.append('### 隐式要求')
    lines.append('')
    lines.append(impl if impl else '无')
    lines.append('')
    lines.append('### 备注')
    lines.append('')
    lines.append(notes if notes else '无')
    lines.append('')
    lines.append('### 项目分支')
    lines.append('')
    folder = 'wrr-' + qid.replace('l1-0', '').replace('l1-', '')
    lines.append('- `wrr-*-qwen`')
    lines.append('- `wrr-*-claude`')
    lines.append('')
    lines.append('---')
    lines.append('')

md = '\n'.join(lines)
with open(r'd:\work\github\robust\docs\题目0607.md', 'w', encoding='utf-8') as f:
    f.write(md)

print('Written %d questions to 题目0607.md' % len(rows))
