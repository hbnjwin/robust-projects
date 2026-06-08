import sqlite3, os

db_path = os.path.join(os.environ['LOCALAPPDATA'], 'robust-manager', 'robust_manager.db')
conn = sqlite3.connect(db_path)

cur = conn.execute("SELECT question_id FROM questions WHERE question_id='l1-002'")
rows = cur.fetchall()
if rows:
    print("l1-002 exists")
else:
    print("l1-002 MISSING - inserting...")
    conn.execute(
        "INSERT INTO questions (question_id, query, task_type, app_domain, language, weight, implicit_requirements, notes, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('l1-002',
         'Flutter 应用中，下拉刷新时列表会意外跳动到顶部。请定位 RefreshIndicator 与 ScrollController 的交互 bug，修复后确保下拉刷新时列表位置保持不变，并添加刷新状态指示器。',
         'bug-fix', 'mobile_app', 'other', 9.7,
         '需要理解 Flutter 的 RefreshIndicator 和 ScrollController 机制',
         'Flutter/Dart 项目', 'draft')
    )
    conn.commit()
    print("l1-002 inserted")

cur = conn.execute("SELECT COUNT(*) FROM questions")
print("Total questions: %d" % cur.fetchone()[0])
conn.close()
