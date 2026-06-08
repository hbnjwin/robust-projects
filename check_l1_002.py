import sqlite3

db_path = r'C:\Users\wt.home\AppData\Local\robust-manager\robust_manager.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT question_id, task_type, app_domain, language, weight FROM questions WHERE question_id = 'l1-002'")
row = c.fetchone()
if row:
    print("Found l1-002: %s | %s | %s | %s | %s" % (row[0], row[1], row[2], row[3], row[4]))
else:
    print("l1-002 not found!")
c.execute("SELECT COUNT(*) FROM questions")
print("Total: %d" % c.fetchone()[0])
conn.close()
