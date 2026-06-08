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

for r in rows:
    qid, query, tt, ad, lang, w, impl, notes, status = r
    print('=' * 80)
    print('ID: %s' % qid)
    print('Type: %s | Domain: %s | Lang: %s | Weight: %.1f' % (tt, ad, lang, w))
    print('Query: %s' % query)
    print('Implicit: %s' % (impl or ''))
    print('Notes: %s' % (notes or ''))
    print()
