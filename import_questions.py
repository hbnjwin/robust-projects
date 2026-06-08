import sqlite3
import json

db_path = r'C:\Users\wt.home\AppData\Local\robust-manager\robust_manager.db'
json_path = r'D:\work\github\robust\robust-projects\questions.json'

conn = sqlite3.connect(db_path)
c = conn.cursor()

with open(json_path, 'r', encoding='utf-8') as f:
    questions = json.load(f)

inserted = 0
skipped = 0

for q in questions:
    try:
        c.execute("""
            INSERT OR IGNORE INTO questions 
            (question_id, query, task_type, app_domain, language, weight,
             implicit_requirements, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            q['question_id'],
            q['query'],
            q['task_type'],
            q['app_domain'],
            q['language'],
            q['weight'],
            q.get('implicit_requirements', ''),
            q.get('notes', ''),
            q.get('status', 'draft'),
        ))
        if c.rowcount > 0:
            inserted += 1
            print(f"Inserted: {q['question_id']}")
        else:
            skipped += 1
            print(f"Skipped (exists): {q['question_id']}")
    except Exception as e:
        print(f"Error inserting {q['question_id']}: {e}")

conn.commit()

c.execute("SELECT COUNT(*) FROM questions")
total = c.fetchone()[0]
print(f"\nInserted: {inserted}, Skipped: {skipped}, Total in DB: {total}")

conn.close()
