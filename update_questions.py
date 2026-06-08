import sqlite3
import json

db_path = r'C:\Users\wt.home\AppData\Local\robust-manager\robust_manager.db'
json_path = r'D:\work\github\robust\robust-projects\questions.json'

conn = sqlite3.connect(db_path)
c = conn.cursor()

with open(json_path, 'r', encoding='utf-8') as f:
    questions = json.load(f)

updated = 0
for q in questions:
    c.execute(
        "UPDATE questions SET query=?, task_type=?, app_domain=?, language=?, weight=?, implicit_requirements=?, notes=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE question_id=?",
        (q['query'], q['task_type'], q['app_domain'], q['language'], q['weight'],
         q.get('implicit_requirements', ''), q.get('notes', ''), q.get('status', 'draft'), q['question_id']))
    if c.rowcount > 0:
        updated += 1
        print("Updated: " + q['question_id'])

conn.commit()
c.execute("SELECT question_id, task_type, app_domain, language, weight FROM questions ORDER BY question_id")
rows = c.fetchall()
print("\nUpdated: %d" % updated)
print("Total questions in DB: %d" % len(rows))
for r in rows:
    print("  %s | %s | %s | %s | %s" % (r[0], r[1], r[2], r[3], r[4]))
conn.close()
