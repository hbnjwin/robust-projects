import subprocess
import os
import json
import sqlite3

REPO_DIR = r'D:\work\github\robust\robust-projects'

db_path = os.path.join(os.environ['LOCALAPPDATA'], 'robust-manager', 'robust_manager.db')
conn = sqlite3.connect(db_path)
cur = conn.execute(
    'SELECT question_id, query, task_type, app_domain, language, weight, '
    'implicit_requirements FROM questions ORDER BY question_id'
)
rows = cur.fetchall()
conn.close()

questions = {}
for r in rows:
    qid, query, tt, ad, lang, w, impl = r
    questions[qid] = {
        'query': query, 'task_type': tt, 'app_domain': ad,
        'language': lang, 'weight': w, 'implicit': impl
    }

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

CLAUDE_MD_CONFIG = {
    'l1-001': {
        'content': '# Project Rules\n\n## Coding Standards\n- All React components must use functional components with TypeScript\n- State updates must be immutable\n- All bug fixes must include corresponding unit tests\n\n## Testing\n- Run `npm test` before committing\n- Test files must be co-located with source files (e.g., `TableWithFilter.test.tsx`)\n- Use `@testing-library/react` for component tests\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-002': {
        'content': '# Project Rules\n\n## Flutter Standards\n- Follow effective dart guidelines\n- All bug fixes must be tested on both iOS and Android\n- Use `flutter test` before committing\n\n## Testing\n- Widget tests required for all UI changes\n- Test files in `test/` directory mirroring `lib/` structure\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-003': {
        'content': '# Project Rules\n\n## Vue Standards\n- Follow Vue 2 style guide\n- Component data must be a function\n- All bug fixes must include corresponding tests\n\n## Testing\n- Run `npm run test:unit` before committing\n- Use `@vue/test-utils` for component tests\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-004': {
        'content': '# Project Rules\n\n## Java/Spring Standards\n- Follow Spring Boot best practices\n- All service methods must handle concurrency explicitly\n- Thread safety documentation required for shared state\n\n## Testing\n- Run `mvn test` before committing\n- Concurrent tests must use `@SpringBootTest` with `@DirtiesContext`\n- Test coverage must not decrease\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-005': {
        'content': '# Project Rules\n\n## Data Pipeline Standards\n- All transforms must handle schema evolution gracefully\n- Never throw raw exceptions in pipeline - use structured error handling\n- Log all schema changes with before/after comparison\n\n## Testing\n- Run `mvn test` before committing\n- Include tests for both old and new schema formats\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-006': {
        'content': '# Project Rules\n\n## Testing Standards\n- Read `TESTING_GUIDE.md` before modifying any test files\n- All Selenium tests must use explicit waits, never `time.sleep()`\n- CI test failures must include screenshot on failure\n\n## Testing\n- Run `pytest --ci` to simulate CI environment\n- Use `conftest.py` fixtures for driver setup\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-007': {
        'content': '# Project Rules\n\n## API Standards\n- All new endpoints must be idempotent where applicable\n- Payment-related APIs must include rate limiting\n- Exception handling must use `@ControllerAdvice`\n\n## Testing\n- Run `mvn test` before committing\n- Payment tests must extend `PaymentTestBase`\n- List all executed test commands in final response\n\n## Commit\n- Commit message format: `feat(scope): description`\n'
    },
    'l1-008': {
        'content': '# Project Rules\n\n## Unity Standards\n- All AI behavior changes must include NavMesh validation\n- Debug visualizations must be behind `#if UNITY_EDITOR` guards\n- Performance profiling required for AI changes\n\n## Testing\n- Test in both Editor and Build\n- Verify no regression in normal patrol behavior\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-009': {
        'content': '# Project Rules\n\n## Android Standards\n- Follow Android Jetpack guidelines\n- All list adapters must handle pagination properly\n- RecyclerView changes must not introduce memory leaks\n\n## Testing\n- Run `./gradlew test` before committing\n- Include tests for edge cases (empty list, rapid scroll)\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-010': {
        'content': '# Project Rules\n\n## CSS/Mobile Standards\n- All layouts must be tested on 320px-428px width\n- Use `env(safe-area-inset-*)` for notched devices\n- CSS must include graceful degradation for older browsers\n- Never use `!important` without documentation\n\n## Testing\n- Test on Chrome DevTools device emulation\n- Verify both portrait and landscape orientations\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-011': {
        'content': '# Project Rules\n\n## Import Feature Standards\n- All file imports must handle encoding gracefully (UTF-8, GBK, GB2312)\n- Large files (>10MB) must use streaming/chunked reading\n- Import results must include a downloadable report\n- Never ask users to manually reformat their files\n\n## Testing\n- Run `npm test` before committing\n- Include tests for various Excel formats (.xlsx, .xls, .csv)\n\n## Commit\n- Commit message format: `feat(scope): description`\n'
    },
    'l1-012': {
        'content': '# Project Rules\n\n## C Standards\n- All memory allocations must have corresponding frees\n- Use valgrind to verify no memory leaks after fixes\n- Add memory monitoring logs for long-running processes\n\n## Testing\n- Run with valgrind: `valgrind --leak-check=full ./gateway`\n- Verify stable memory usage over 24h period\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-013': {
        'content': '# Project Rules\n\n## Database Standards\n- All query optimizations must include `explain()` output comparison\n- Index changes must be reviewed for write performance impact\n- Cache invalidation must follow the project cache strategy in `CACHE_POLICY.md`\n\n## Testing\n- Run `pytest` before committing\n- Include slow query benchmarks before/after\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-014': {
        'content': '# Project Rules\n\n## gRPC Standards\n- Client and server timeout must be aligned (server > client)\n- All timeout changes must include retry strategy documentation\n- Check upstream gRPC version compatibility before changes\n\n## Testing\n- Run `go test ./...` before committing\n- Include integration tests for timeout scenarios\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-015': {
        'content': '# Project Rules\n\n## API Encoding Standards\n- All endpoints must handle UTF-8 encoding explicitly\n- File upload endpoints must support RFC 5987 for filenames\n- CORS preflight must handle Content-Type with charset\n- Never assume client encoding matches server encoding\n\n## Testing\n- Run `pytest` before committing\n- Include tests for Chinese characters in URL params, body, and filenames\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-016': {
        'content': '# Project Rules\n\n## Data Platform Standards\n- All visualizations must handle >10k nodes without freezing\n- Graph layouts must support expand/collapse interaction\n- Export reports must be in both PDF and CSV formats\n\n## Testing\n- Run `pytest` before committing\n- Include performance benchmarks for large datasets\n\n## Commit\n- Commit message format: `feat(scope): description`\n'
    },
    'l1-017': {
        'content': '# Project Rules\n\n## ML Project Standards\n- Refactoring must preserve training results exactly (same seed = same output)\n- All modules must be independently testable\n- Configuration must be externalized to yaml/json files\n- Add README.md for each new module\n\n## Testing\n- Run `python -m pytest` before committing\n- Verify training produces identical metrics after refactor\n\n## Commit\n- Commit message format: `refactor(scope): description`\n'
    },
    'l1-018': {
        'content': '# Project Rules\n\n## ETL Standards\n- All transforms must handle schema evolution gracefully\n- Never break downstream consumers with format changes\n- Schema changes must be logged with migration notes\n\n## Testing\n- Run `pytest` before committing\n- Include tests for both old and new data formats\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-019': {
        'content': '# Project Rules\n\n## Frontend Interaction Standards\n- All drag-and-drop must support touch events for mobile\n- State changes must be persisted (not lost on refresh)\n- Include undo/redo support for destructive actions\n- WCAG 2.1 AA accessibility required\n\n## Testing\n- Run `npm test` before committing\n- Test on both desktop and mobile viewports\n\n## Commit\n- Commit message format: `feat(scope): description`\n'
    },
    'l1-020': {
        'content': '# Project Rules\n\n## ML Inference Standards\n- GPU memory must be released after inference batch completes\n- Never use `torch.cuda.empty_cache()` as the primary fix\n- Add GPU memory monitoring script for verification\n- Batch size must be configurable\n\n## Testing\n- Run `python -m pytest` before committing\n- Verify GPU memory returns to baseline after inference\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-021': {
        'content': '# Project Rules\n\n## React Native Standards\n- Navigation state must be preserved across screen transitions\n- Android back button must be handled explicitly\n- All navigation changes must include logging for debugging\n- Never restructure existing route hierarchy without documentation\n\n## Testing\n- Run `npm test` before committing\n- Test on both iOS and Android simulators\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-022': {
        'content': '# Project Rules\n\n## DevOps Platform Standards\n- Read `ALERT_POLICY.md` before implementing any alerting feature\n- All alert rules must support hot-reload without service restart\n- Alert aggregation must use root-cause analysis (not simple dedup)\n- Silent period configuration must be respected\n- Auto-recovery must include rollback mechanism\n\n## Testing\n- Run `pytest` before committing\n- Test alert aggregation with simulated cascading failures\n\n## Commit\n- Commit message format: `feat(scope): description`\n'
    },
    'l1-023': {
        'content': '# Project Rules\n\n## Mini Program Standards\n- All time-sensitive operations must use server time, never client time\n- Concurrent requests must be handled with idempotency\n- Offline actions must queue and sync when online\n- Timezone handling must be explicit\n\n## Testing\n- Run `npm test` before committing\n- Test with manipulated client clock\n\n## Commit\n- Commit message format: `feat(scope): description`\n'
    },
    'l1-024': {
        'content': '# Project Rules\n\n## Testing Standards\n- Read `TESTING_GUIDE.md` before modifying any test files\n- All new tests must extend `PaymentTestBase`\n- Test naming convention: `methodUnderTest_scenario_expectedResult`\n- Final response must list all executed test commands\n- Mock all external dependencies, never call real services\n\n## Testing\n- Run `mvn test` before committing\n- Coverage must increase from current 30%+\n\n## Commit\n- Commit message format: `test(scope): description`\n'
    },
    'l1-025': {
        'content': '# Project Rules\n\n## Game Script Standards\n- All event handlers must be idempotent (prevent double-fire)\n- Combat changes must not affect other skills\n- Add combat logging for debugging\n- Performance profiling required for combat system changes\n\n## Testing\n- Test all skill combinations after changes\n- Verify no regression in other skill damage calculations\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-026': {
        'content': '# Project Rules\n\n## Data Warehouse Standards\n- All SQL changes must include data validation output\n- Deduplication must happen before aggregation\n- ETL schedule must not be affected by new validation steps\n- Anomaly thresholds must be configurable\n\n## Testing\n- Run `pytest` before committing\n- Verify retention calculation matches manual calculation\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-027': {
        'content': '# Project Rules\n\n## Security/Permission Standards\n- All permission annotations must be validated by integration tests\n- Role hierarchy must follow: parent role >= child role permissions\n- Cache invalidation must be triggered on permission changes\n- Permission changes must be logged with audit trail\n\n## Testing\n- Run `mvn test` before committing\n- Include tests for role inheritance edge cases\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-028': {
        'content': '# Project Rules\n\n## Frontend Standards\n- All comparison tables must handle dynamic parameter sets\n- Mobile layout must use sticky headers and horizontal scroll\n- URL must reflect current comparison state (shareable)\n- Support 2-4 products in comparison\n\n## Testing\n- Run `npm test` before committing\n- Test on mobile viewport (375px width)\n\n## Commit\n- Commit message format: `feat(scope): description`\n'
    },
    'l1-029': {
        'content': '# Project Rules\n\n## CI/CD Standards\n- Read `CI_CONFIG_GUIDE.md` before modifying build scripts\n- Cache keys must include branch namespace to prevent cross-branch conflicts\n- All build script changes must include build time comparison report\n- Mirror source configuration must support fallback\n\n## Testing\n- Test build with `--dry-run` before committing\n- Verify cache hit rate improvement\n\n## Commit\n- Commit message format: `fix(scope): description`\n'
    },
    'l1-030': {
        'content': '# Project Rules\n\n## ML Serving Standards\n- A/B traffic splitting must be by user features, not pure random\n- Experiment groups must be isolated (no data contamination)\n- Statistical significance must be calculated automatically\n- Traffic ratio changes must not require service restart\n- Flow coloring must propagate through service chain\n\n## Testing\n- Run `pytest` before committing\n- Test traffic splitting with various user profiles\n\n## Commit\n- Commit message format: `feat(scope): description`\n'
    },
}

SKILL_CONFIG = {
    'l1-022': {
        'dir': '.claude/skills',
        'filename': 'auto-patrol-workflow.md',
        'content': '# Auto Patrol Workflow Skill\n\n## Mandatory Steps\n1. Confirm monitoring environment is accessible\n2. Define patrol check rules (read from config)\n3. Implement health check logic for each service\n4. Implement alert aggregation with root-cause analysis\n5. Configure silent periods\n6. Implement hot-reload for patrol rules\n7. Add auto-recovery with rollback\n8. Generate patrol report\n9. Verify end-to-end flow\n\n## Checklist\n- [ ] Environment accessible\n- [ ] Health check implemented\n- [ ] Alert aggregation (not simple dedup)\n- [ ] Silent period configurable\n- [ ] Hot-reload working\n- [ ] Auto-recovery + rollback\n- [ ] Report generated\n'
    },
    'l1-024': {
        'dir': '.claude/skills',
        'filename': 'testing-workflow.md',
        'content': '# Testing Workflow Skill\n\n## Mandatory Steps\n1. Read `TESTING_GUIDE.md` for project testing conventions\n2. Read `CLAUDE.md` for testing rules\n3. Identify untested methods and branches\n4. Create test cases extending `PaymentTestBase`\n5. Mock all external dependencies\n6. Cover exception branches with boundary values\n7. Run all tests and verify coverage increase\n8. List all executed test commands in final response\n\n## Checklist\n- [ ] TESTING_GUIDE.md read\n- [ ] CLAUDE.md rules followed\n- [ ] PaymentTestBase extended\n- [ ] External deps mocked\n- [ ] Exception branches covered\n- [ ] Tests pass\n- [ ] Commands listed\n'
    },
    'l1-029': {
        'dir': '.claude/skills',
        'filename': 'cicd-fix-workflow.md',
        'content': '# CI/CD Fix Workflow Skill\n\n## Mandatory Steps\n1. Read `CI_CONFIG_GUIDE.md` for project CI conventions\n2. Read `CLAUDE.md` for build rules\n3. Analyze current cache key generation logic\n4. Identify root cause of cache misses\n5. Fix cache key with branch namespace isolation\n6. Configure mirror source with fallback\n7. Add retry with exponential backoff\n8. Add cache cleanup strategy (LRU)\n9. Generate build time comparison report\n10. Verify fix with dry-run\n\n## Checklist\n- [ ] CI_CONFIG_GUIDE.md read\n- [ ] Root cause identified\n- [ ] Cache key fixed\n- [ ] Branch namespace isolation\n- [ ] Mirror source configured\n- [ ] Retry strategy added\n- [ ] Build time report generated\n'
    },
}

ATTACHMENT_CONFIG = {
    'l1-011': {
        'dir': 'attachments',
        'files': [
            ('sample_users.xlsx', 'PK\x03\x04\x14\x00\x00\x00\x08\x00'),
            ('import_template.csv', 'id,name,phone,email,status\n1,张三,13800138000,zhangsan@test.com,active\n2,李四,139 0013 9000,lisi@test.com,inactive\n3,张三,13800138000,zhangsan@test.com,active\n'),
        ]
    },
    'l1-025': {
        'dir': 'attachments',
        'files': [
            ('combat_log_sample.txt', '[COMBAT] Player=1001 Skill=FireBall Target=Monster_001 Damage=150\n[COMBAT] Player=1001 Skill=FireBall Target=Monster_001 Damage=150\n[COMBAT] Player=1001 Skill=IceLance Target=Monster_002 Damage=80\n'),
        ]
    },
    'l1-026': {
        'dir': 'attachments',
        'files': [
            ('retention_query.sql', '-- Current retention calculation (has bugs)\nSELECT\n  first_day,\n  COUNT(DISTINCT CASE WHEN day_diff = 1 THEN user_id END) as d1_retention,\n  COUNT(DISTINCT CASE WHEN day_diff = 7 THEN user_id END) as d7_retention\nFROM (\n  SELECT\n    user_id,\n    first_day,\n    DATEDIFF(activity_date, first_day) as day_diff\n  FROM user_activity\n) t\nGROUP BY first_day;\n'),
        ]
    },
}

ENV_ISSUE_CONFIG = {
    'l1-006': {
        'files': [
            ('TESTING_GUIDE.md', '# Testing Guide\n\n## Selenium Test Standards\n- Always use explicit waits: `WebDriverWait(driver, timeout).until(...)`\n- Never use `time.sleep()` in tests\n- Use `conftest.py` for shared fixtures\n- CI uses headless Chrome 120\n- Screenshot on failure: `driver.save_screenshot(f"failures/{test_name}.png")`\n\n## CI Environment\n- Python 3.9 (not 3.11)\n- ChromeDriver must match Chrome version\n- Use `--headless=new` flag\n'),
        ],
        'modify_files': {
            'requirements.txt': 'selenium==4.15.0\npytest==7.4.0\nwebdriver-manager==4.0.0\n# NOTE: chromedriver-autoinstaller is NOT included - must handle driver setup manually\n'
        }
    },
    'l1-020': {
        'files': [
            ('environment.yml', 'name: infer-service\nchannels:\n  - pytorch\n  - nvidia\n  - defaults\ndependencies:\n  - python=3.9\n  - pytorch=2.1.0\n  - cudatoolkit=11.8\n  - pip:\n    - fastapi>=0.104.0\n    - uvicorn>=0.24.0\n'),
        ],
        'modify_files': {
            'requirements.txt': 'torch==2.1.0\nfastapi>=0.104.0\nuvicorn>=0.24.0\n# NOTE: CUDA toolkit version must match - check with nvidia-smi\n# Missing: gpustat for monitoring - install manually if needed\n'
        }
    },
    'l1-017': {
        'files': [
            ('environment.yml', 'name: ml-training\nchannels:\n  - pytorch\n  - defaults\ndependencies:\n  - python=3.9\n  - pytorch=2.1.0\n  - pip:\n    - scikit-learn>=1.3.0\n    - matplotlib>=3.7.0\n    - tensorboard>=2.15.0\n'),
        ],
        'modify_files': {
            'requirements.txt': 'torch==2.1.0\nscikit-learn>=1.3.0\n# NOTE: matplotlib and tensorboard are missing from requirements.txt\n# Install from environment.yml: conda env create -f environment.yml\n'
        }
    },
    'l1-029': {
        'files': [
            ('CI_CONFIG_GUIDE.md', '# CI/CD Configuration Guide\n\n## Build Cache\n- Cache key must include: branch name, dependency hash, and build target\n- Cache namespace: `${BRANCH_NAME}-${HASH}`\n- Never share cache across branches\n\n## Mirror Sources\n- Primary: registry.npmmirror.com\n- Fallback: registry.npmjs.org\n\n## Build Script\n- Build command: `npm run build`\n- Cache directory: `.cache/build`\n- Artifact directory: `dist/`\n'),
        ],
    },
    'l1-013': {
        'files': [
            ('CACHE_POLICY.md', '# Cache Policy\n\n## Cache Invalidation\n- Write-through: update cache immediately on DB write\n- TTL: 300 seconds for query results\n- Invalidation trigger: any write operation on the collection\n- Cache key format: `query:{collection}:{hash(filter_params)}`\n\n## Consistency\n- Read-after-write must return latest data\n- Stale cache must be detectable via version field\n'),
        ],
    },
}

def run_git(args, cwd=REPO_DIR):
    result = subprocess.run(['git'] + args, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return result

def update_branch(branch_name, qid, model):
    folder = FOLDER_MAP.get(qid)
    if not folder:
        print("  SKIP: no folder map for %s" % qid)
        return False

    proj_dir = os.path.join(REPO_DIR, 'projects', '%s-%s' % (folder, model))

    result = run_git(['checkout', branch_name])
    if result.returncode != 0:
        print("  FAIL checkout %s: %s" % (branch_name, result.stderr.strip()))
        return False

    os.makedirs(proj_dir, exist_ok=True)

    changed = False

    # 1. Update README.md with current query
    q = questions.get(qid, {})
    readme_path = os.path.join(proj_dir, 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        new_readme = '# %s\n\n## Question ID: %s\n\n## Task Type: %s\n\n## App Domain: %s\n\n## Language: %s\n\n## Model: %s\n\n## Query\n\n%s\n' % (
            folder, qid, q.get('task_type', ''), q.get('app_domain', ''),
            q.get('language', ''), model, q.get('query', '')
        )
        if content != new_readme:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(new_readme)
            changed = True

    # 2. Add CLAUDE.md
    claude_cfg = CLAUDE_MD_CONFIG.get(qid)
    if claude_cfg:
        claude_path = os.path.join(proj_dir, 'CLAUDE.md')
        with open(claude_path, 'w', encoding='utf-8') as f:
            f.write(claude_cfg['content'])
        changed = True

    # 3. Add skill files
    skill_cfg = SKILL_CONFIG.get(qid)
    if skill_cfg:
        skill_dir = os.path.join(proj_dir, skill_cfg['dir'])
        os.makedirs(skill_dir, exist_ok=True)
        skill_path = os.path.join(skill_dir, skill_cfg['filename'])
        with open(skill_path, 'w', encoding='utf-8') as f:
            f.write(skill_cfg['content'])
        changed = True

    # 4. Add attachment files
    attach_cfg = ATTACHMENT_CONFIG.get(qid)
    if attach_cfg:
        attach_dir = os.path.join(proj_dir, attach_cfg['dir'])
        os.makedirs(attach_dir, exist_ok=True)
        for fname, fcontent in attach_cfg['files']:
            fpath = os.path.join(attach_dir, fname)
            if fname.endswith('.xlsx'):
                with open(fpath, 'wb') as f:
                    f.write(b'PK\x03\x04\x14\x00\x00\x00\x08\x00')
            else:
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(fcontent)
        changed = True

    # 5. Add environment issue files
    env_cfg = ENV_ISSUE_CONFIG.get(qid)
    if env_cfg:
        for fname, fcontent in env_cfg.get('files', []):
            fpath = os.path.join(proj_dir, fname)
            os.makedirs(os.path.dirname(fpath), exist_ok=True) if os.path.dirname(fpath) else None
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(fcontent)
            changed = True
        for fname, fcontent in env_cfg.get('modify_files', {}).items():
            fpath = os.path.join(proj_dir, fname)
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(fcontent)
            changed = True

    if changed:
        run_git(['add', '.'])
        run_git(['commit', '-m', 'chore: add bad pattern triggers (CLAUDE.md/skills/attachments/env) for %s' % qid])

    return changed

success = 0
fail = 0
skip = 0

for qid in sorted(FOLDER_MAP.keys()):
    folder = FOLDER_MAP[qid]
    for model in ['qwen', 'claude']:
        branch = '%s-%s' % (folder, model)
        print("Processing %s (%s)..." % (branch, qid))
        try:
            result = update_branch(branch, qid, model)
            if result:
                success += 1
                print("  UPDATED")
            else:
                skip += 1
                print("  SKIP (no changes)")
        except Exception as e:
            fail += 1
            print("  ERROR: %s" % str(e))

run_git(['checkout', 'master'])

print("\n" + "=" * 60)
print("Results: %d updated, %d skipped, %d failed" % (success, skip, fail))
