import sqlite3
import os

db_path = os.path.join(os.environ['LOCALAPPDATA'], 'robust-manager', 'robust_manager.db')
conn = sqlite3.connect(db_path)
cur = conn.execute(
    'SELECT question_id, query, task_type, app_domain, language, weight, '
    'implicit_requirements FROM questions ORDER BY question_id'
)
rows = cur.fetchall()
conn.close()

for r in rows:
    qid, query, tt, ad, lang, w, impl = r
    print('=' * 80)
    print('ID: %s | %s | %s | %s | W:%.1f' % (qid, tt, ad, lang, w))
    print('Query: %s' % query)
    print('Implicit:')
    if impl:
        for item in impl.split('；'):
            item = item.strip()
            if item:
                print('  - %s' % item)
    else:
        print('  (none)')
    print()
