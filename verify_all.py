import sqlite3
import os
import subprocess

db_path = r'C:\Users\wt.home\AppData\Local\robust-manager\robust_manager.db'
projects_dir = r'D:\work\github\robust\robust-projects\projects'
repo_dir = r'D:\work\github\robust\robust-projects'

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

conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT question_id, task_type, app_domain, language, weight, status FROM questions ORDER BY question_id")
db_questions = c.fetchall()
conn.close()

result = subprocess.run(['git', 'branch', '--list'], capture_output=True, text=True, cwd=repo_dir)
branches = [b.strip().lstrip('* ').strip() for b in result.stdout.strip().split('\n') if b.strip()]

print("=" * 80)
print("VERIFICATION REPORT")
print("=" * 80)

print("\n1. DATABASE QUESTIONS: %d" % len(db_questions))
for q in db_questions:
    print("   %s | %s | %s | %s | %.1f | %s" % (q[0], q[1], q[2], q[3], q[4], q[5]))

print("\n2. PROJECT FOLDERS:")
folder_ok = 0
folder_missing = 0
for qid, prefix in FOLDER_MAP.items():
    qwen_dir = os.path.join(projects_dir, prefix + '-qwen')
    claude_dir = os.path.join(projects_dir, prefix + '-claude')
    qwen_ok = os.path.isdir(qwen_dir)
    claude_ok = os.path.isdir(claude_dir)
    if qwen_ok and claude_ok:
        folder_ok += 1
    else:
        folder_missing += 1
        print("   MISSING: %s qwen=%s claude=%s" % (qid, qwen_ok, claude_ok))
print("   Folders OK: %d/30, Missing: %d" % (folder_ok, folder_missing))

print("\n3. GIT BRANCHES:")
branch_ok = 0
branch_missing = 0
for qid, prefix in FOLDER_MAP.items():
    qwen_branch = prefix + '-qwen'
    claude_branch = prefix + '-claude'
    qwen_ok = qwen_branch in branches
    claude_ok = claude_branch in branches
    if qwen_ok and claude_ok:
        branch_ok += 1
    else:
        branch_missing += 1
        print("   MISSING: %s qwen=%s claude=%s" % (qid, qwen_ok, claude_ok))
print("   Branches OK: %d/30, Missing: %d" % (branch_ok, branch_missing))

print("\n" + "=" * 80)
print("SUMMARY: DB=%d, Folders=%d/30, Branches=%d/30" % (len(db_questions), folder_ok, branch_ok))
if folder_ok == 30 and branch_ok == 30 and len(db_questions) == 30:
    print("ALL CHECKS PASSED!")
else:
    print("SOME CHECKS FAILED - SEE ABOVE")
print("=" * 80)
