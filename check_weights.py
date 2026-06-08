import sqlite3
import os

db_path = os.path.join(os.environ['LOCALAPPDATA'], 'robust-manager', 'robust_manager.db')
conn = sqlite3.connect(db_path)

cur = conn.execute("SELECT question_id, task_type, app_domain, language, weight FROM questions ORDER BY question_id")
rows = cur.fetchall()

WEIGHT_TABLE = {
    ('bug-fix', 'web_frontend', 'ts'): 10.0,
    ('bug-fix', 'mobile_app', 'other'): 9.7,
    ('bug-fix', 'web_frontend', 'js'): 9.5,
    ('bug-fix', 'backend_service', 'java'): 9.4,
    ('bug-fix', 'data_engineering', 'java'): 9.4,
    ('bug-fix', 'devtools_test', 'python'): 9.4,
    ('feature', 'backend_service', 'java'): 9.2,
    ('bug-fix', 'game_dev', 'other'): 9.1,
    ('bug-fix', 'mobile_app', 'java'): 9.0,
    ('bug-fix', 'web_frontend', 'html/css'): 8.7,
    ('feature', 'web_frontend', 'js'): 8.6,
    ('bug-fix', 'backend_service', 'c'): 8.2,
    ('bug-fix', 'database_storage', 'python'): 8.2,
    ('bug-fix', 'backend_service', 'go'): 8.0,
    ('bug-fix', 'backend_service', 'python'): 7.9,
    ('feature', 'data_engineering', 'python'): 7.9,
    ('refactor-maintenance', 'ai_ml', 'python'): 7.9,
    ('bug-fix', 'data_engineering', 'python'): 7.8,
    ('feature', 'web_frontend', 'ts'): 7.7,
    ('bug-fix', 'ai_ml', 'python'): 7.6,
    ('code-explanation', 'mobile_app', 'other'): 7.5,
    ('feature', 'devops_infrastructure', 'python'): 7.2,
    ('feature', 'mobile_app', 'other'): 7.2,
    ('testing-quality', 'backend_service', 'java'): 7.1,
    ('bug-fix', 'game_dev', 'lua'): 7.0,
    ('code-explanation', 'data_engineering', 'python'): 7.0,
    ('code-explanation', 'backend_service', 'java'): 7.0,
    ('feature', 'web_frontend', 'html/css'): 7.0,
    ('build-release-config', 'devops_infrastructure', 'shell'): 6.9,
    ('feature', 'ai_ml', 'python'): 6.8,
}

print("Checking weight consistency:")
print("%-8s | %-25s | %-22s | %-8s | %6s | %6s | %s" % ('ID', 'Type', 'Domain', 'Lang', 'DB_W', 'Table_W', 'Match'))
print('-' * 110)

for r in rows:
    qid, tt, ad, lang, db_w = r
    key = (tt, ad, lang)
    table_w = WEIGHT_TABLE.get(key, None)
    match = 'OK' if table_w is None or abs(db_w - table_w) < 0.01 else 'MISMATCH'
    if match == 'MISMATCH':
        conn.execute("UPDATE questions SET weight=? WHERE question_id=?", (table_w, qid))
        print("%-8s | %-25s | %-22s | %-8s | %6.1f | %6.1f | %s -> FIXED" % (qid, tt, ad, lang, db_w, table_w, match))
    else:
        print("%-8s | %-25s | %-22s | %-8s | %6.1f | %6s | %s" % (qid, tt, ad, lang, db_w, str(table_w) if table_w else 'N/A', match))

conn.commit()
conn.close()
print("\nDone!")
