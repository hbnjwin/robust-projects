import os
import subprocess
import time

BASE = r'D:\work\github\robust\robust-projects'

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

def run_git(*args):
    result = subprocess.run(['git'] + list(args), capture_output=True, text=True, cwd=BASE)
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def commit_to_branch(branch_name, folder_name):
    rc, out, err = run_git('checkout', branch_name)
    if rc != 0:
        print("  FAIL checkout %s: %s" % (branch_name, err[:200]))
        return False

    run_git('add', '-f', '.gitignore')
    run_git('add', '-f', os.path.join('projects', folder_name))

    rc, out, err = run_git('status', '--porcelain')
    if not out.strip():
        print("  SKIP %s (nothing to commit)" % branch_name)
        return True

    rc, out, err = run_git('commit', '-m', 'Add project skeleton for %s' % folder_name)
    if rc != 0:
        if 'nothing to commit' in out or 'nothing to commit' in err:
            print("  SKIP %s (nothing to commit)" % branch_name)
        else:
            print("  FAIL commit %s: %s" % (branch_name, (out + err)[:200]))
    else:
        print("  OK committed %s" % branch_name)

    for attempt in range(3):
        rc, out, err = run_git('push', 'origin', branch_name)
        if rc == 0:
            print("  OK pushed %s" % branch_name)
            break
        else:
            print("  RETRY push %s (attempt %d): %s" % (branch_name, attempt+1, err[:100]))
            time.sleep(3)

    return True

success = 0
fail = 0
for qid, folder in FOLDER_MAP.items():
    for model in ['qwen', 'claude']:
        branch = folder + '-' + model
        folder_full = folder + '-' + model
        print("Processing: %s" % branch)
        if commit_to_branch(branch, folder_full):
            success += 1
        else:
            fail += 1

run_git('checkout', 'master')
print("\nDone! Success: %d, Fail: %d" % (success, fail))
