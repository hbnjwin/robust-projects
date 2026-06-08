import subprocess

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

missing_skeleton = []
has_skeleton = []

for qid, folder in FOLDER_MAP.items():
    for model in ['qwen', 'claude']:
        branch = folder + '-' + model
        rc, out, err = run_git('log', '--oneline', '-5', branch)
        if 'Add project skeleton' in out:
            has_skeleton.append(branch)
        else:
            missing_skeleton.append(branch)
            print("NO SKELETON: %s" % branch)
            print("  Log: %s" % out[:200])

print("\nHas skeleton: %d" % len(has_skeleton))
print("Missing skeleton: %d" % len(missing_skeleton))
if missing_skeleton:
    print("\nMissing branches:")
    for b in missing_skeleton:
        print("  %s" % b)
