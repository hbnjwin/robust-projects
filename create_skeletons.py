import os
import json

BASE = r'D:\work\github\robust\robust-projects\projects'

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def create_skeleton(folder_name, task_type, app_domain, language, query, question_id):
    qwen_dir = os.path.join(BASE, folder_name + '-qwen')
    claude_dir = os.path.join(BASE, folder_name + '-claude')

    for target_dir in [qwen_dir, claude_dir]:
        model = 'qwen' if 'qwen' in target_dir else 'claude'
        write_file(os.path.join(target_dir, 'README.md'),
            f"# {folder_name}\n\n"
            f"## Question ID: {question_id}\n\n"
            f"## Task Type: {task_type}\n\n"
            f"## App Domain: {app_domain}\n\n"
            f"## Language: {language}\n\n"
            f"## Model: {model}\n\n"
            f"## Query\n\n{query}\n"
        )

        if task_type == 'bug-fix' and app_domain == 'web_frontend' and language == 'ts':
            create_ts_web_bugfix(target_dir)
        elif task_type == 'bug-fix' and app_domain == 'mobile_app' and language == 'other':
            create_flutter_bugfix(target_dir)
        elif task_type == 'bug-fix' and app_domain == 'web_frontend' and language == 'js':
            create_js_web_bugfix(target_dir)
        elif task_type == 'bug-fix' and app_domain == 'backend_service' and language == 'java':
            create_java_backend_bugfix(target_dir)
        elif task_type == 'bug-fix' and app_domain == 'data_engineering' and language == 'java':
            create_java_data_bugfix(target_dir)
        elif task_type == 'bug-fix' and app_domain == 'devtools_test' and language == 'python':
            create_python_test_bugfix(target_dir)
        elif task_type == 'feature' and app_domain == 'backend_service' and language == 'java':
            create_java_backend_feature(target_dir)
        elif task_type == 'bug-fix' and app_domain == 'game_dev' and language == 'other':
            create_unity_game_bugfix(target_dir)
        elif task_type == 'bug-fix' and app_domain == 'mobile_app' and language == 'java':
            create_android_bugfix(target_dir)
        elif task_type == 'bug-fix' and app_domain == 'web_frontend' and language == 'html/css':
            create_html_css_bugfix(target_dir)
        elif task_type == 'feature' and app_domain == 'web_frontend' and language == 'js':
            create_js_web_feature(target_dir)
        elif task_type == 'bug-fix' and app_domain == 'backend_service' and language == 'c':
            create_c_backend_bugfix(target_dir)
        elif task_type == 'bug-fix' and app_domain == 'database_storage' and language == 'python':
            create_python_db_bugfix(target_dir)
        elif task_type == 'bug-fix' and app_domain == 'backend_service' and language == 'go':
            create_go_backend_bugfix(target_dir)
        elif task_type == 'bug-fix' and app_domain == 'backend_service' and language == 'python':
            create_python_backend_bugfix(target_dir)
        elif task_type == 'feature' and app_domain == 'data_engineering' and language == 'python':
            create_python_data_feature(target_dir)
        elif task_type == 'refactor-maintenance' and app_domain == 'ai_ml' and language == 'python':
            create_python_ml_refactor(target_dir)
        elif task_type == 'bug-fix' and app_domain == 'data_engineering' and language == 'python':
            create_python_etl_bugfix(target_dir)
        elif task_type == 'feature' and app_domain == 'web_frontend' and language == 'ts':
            create_ts_web_feature(target_dir)
        elif task_type == 'bug-fix' and app_domain == 'ai_ml' and language == 'python':
            create_python_ai_bugfix(target_dir)
        elif task_type == 'code-explanation' and app_domain == 'mobile_app' and language == 'other':
            create_rn_explain(target_dir)
        elif task_type == 'feature' and app_domain == 'devops_infrastructure' and language == 'python':
            create_python_devops_feature(target_dir)
        elif task_type == 'feature' and app_domain == 'mobile_app' and language == 'other':
            create_miniprogram_feature(target_dir)
        elif task_type == 'testing-quality' and app_domain == 'backend_service' and language == 'java':
            create_java_test_quality(target_dir)
        elif task_type == 'bug-fix' and app_domain == 'game_dev' and language == 'lua':
            create_lua_game_bugfix(target_dir)
        elif task_type == 'code-explanation' and app_domain == 'data_engineering' and language == 'python':
            create_python_data_explain(target_dir)
        elif task_type == 'code-explanation' and app_domain == 'backend_service' and language == 'java':
            create_java_explain(target_dir)
        elif task_type == 'feature' and app_domain == 'web_frontend' and language == 'html/css':
            create_html_css_feature(target_dir)
        elif task_type == 'build-release-config' and app_domain == 'devops_infrastructure' and language == 'shell':
            create_shell_cicd(target_dir)
        elif task_type == 'feature' and app_domain == 'ai_ml' and language == 'python':
            create_python_ai_feature(target_dir)


def create_ts_web_bugfix(d):
    write_file(os.path.join(d, 'package.json'), json.dumps({
        "name": "table-filter-paging-bugfix",
        "version": "1.0.0",
        "scripts": {"dev": "vite", "build": "tsc && vite build", "test": "vitest"},
        "dependencies": {"react": "^18.2.0", "antd": "^5.12.0", "ahooks": "^3.7.0"},
        "devDependencies": {"typescript": "^5.3.0", "vite": "^5.0.0", "vitest": "^1.0.0", "@types/react": "^18.2.0"}
    }, indent=2))
    write_file(os.path.join(d, 'tsconfig.json'), json.dumps({"compilerOptions": {"target": "ES2020", "module": "ESNext", "jsx": "react-jsx", "strict": True, "esModuleInterop": True}}, indent=2))
    write_file(os.path.join(d, 'src', 'TableWithFilter.tsx'),
        'import React, { useState } from "react";\n'
        'import { Table, Select, Button } from "antd";\n'
        'import { useRequest } from "ahooks";\n\n'
        'interface UserRecord {\n  id: number;\n  name: string;\n  status: string;\n  email: string;\n}\n\n'
        'const TableWithFilter: React.FC = () => {\n'
        '  const [filters, setFilters] = useState<Record<string, string>>({});\n'
        '  const [pagination, setPagination] = useState({ current: 1, pageSize: 10 });\n\n'
        '  const { data, loading } = useRequest(\n'
        '    () => fetch(`/api/users?status=${filters.status}&page=${pagination.current}&pageSize=${pagination.pageSize}`),\n'
        '    { refreshDeps: [filters, pagination] }\n'
        '  );\n\n'
        '  const handleFilterChange = (value: string) => {\n'
        '    setFilters({ ...filters, status: value });\n'
        '    // BUG: pagination not reset when filter changes\n'
        '  };\n\n'
        '  return (\n'
        '    <div>\n'
        '      <Select onChange={handleFilterChange} placeholder="Filter by status" />\n'
        '      <Table\n'
        '        dataSource={data?.list}\n'
        '        loading={loading}\n'
        '        pagination={{ ...pagination, onChange: (p) => setPagination({ ...pagination, current: p }) }}\n'
        '      />\n'
        '    </div>\n'
        '  );\n'
        '};\n\nexport default TableWithFilter;\n'
    )

def create_flutter_bugfix(d):
    write_file(os.path.join(d, 'pubspec.yaml'),
        'name: refresh_list_app\nversion: 1.0.0\n\n'
        'environment:\n  sdk: ">=3.0.0 <4.0.0"\n\n'
        'dependencies:\n  flutter:\n    sdk: flutter\n  pull_to_refresh: ^2.0.0\n\n'
        'dev_dependencies:\n  flutter_test:\n    sdk: flutter\n'
    )
    write_file(os.path.join(d, 'lib', 'main.dart'),
        "import 'package:flutter/material.dart';\n"
        "import 'package:pull_to_refresh/pull_to_refresh.dart';\n\n"
        "void main() => runApp(const MyApp());\n\n"
        "class MyApp extends StatelessWidget {\n  const MyApp({super.key});\n"
        "  @override\n  Widget build(BuildContext context) {\n"
        "    return MaterialApp(home: const RefreshListPage());\n  }\n}\n\n"
        "class RefreshListPage extends StatefulWidget {\n  const RefreshListPage({super.key});\n"
        "  @override\n  State<RefreshListPage> createState() => _RefreshListPageState();\n}\n\n"
        "class _RefreshListPageState extends State<RefreshListPage> {\n"
        "  final RefreshController _refreshController = RefreshController();\n"
        "  List<String> items = List.generate(20, (i) => 'Item ${i + 1}');\n\n"
        "  void _onRefresh() async {\n"
        "    await Future.delayed(const Duration(seconds: 1));\n"
        "    setState(() {\n"
        "      items = List.generate(20, (i) => 'Refreshed Item ${i + 1}');\n"
        "    });\n"
        "    _refreshController.refreshCompleted();\n"
        "    // BUG: scroll position jumps after refresh on iOS\n"
        "  }\n\n"
        "  @override\n  Widget build(BuildContext context) {\n"
        "    return Scaffold(\n"
        "      appBar: AppBar(title: const Text('List')),\n"
        "      body: SmartRefresher(\n"
        "        controller: _refreshController,\n"
        "        onRefresh: _onRefresh,\n"
        "        child: ListView.builder(\n"
        "          itemCount: items.length,\n"
        "          itemBuilder: (_, i) => ListTile(title: Text(items[i])),\n"
        "        ),\n"
        "      ),\n"
        "    );\n"
        "  }\n}\n"
    )

def create_js_web_bugfix(d):
    write_file(os.path.join(d, 'package.json'), json.dumps({
        "name": "vue-form-stale-bugfix",
        "version": "1.0.0",
        "scripts": {"dev": "vue-cli-service serve", "build": "vue-cli-service build"},
        "dependencies": {"vue": "^2.7.0", "element-ui": "^2.15.0"},
        "devDependencies": {"@vue/cli-service": "^5.0.0"}
    }, indent=2))
    write_file(os.path.join(d, 'src', 'EditDialog.vue'),
        '<template>\n  <el-dialog :visible.sync="visible" title="Edit" @close="handleClose">\n'
        '    <el-form :model="form" ref="editForm">\n'
        '      <el-form-item label="Name"><el-input v-model="form.name" /></el-form-item>\n'
        '      <el-form-item label="Email"><el-input v-model="form.email" /></el-form-item>\n'
        '      <el-form-item label="Status"><el-select v-model="form.status"><el-option label="Active" value="active" /><el-option label="Inactive" value="inactive" /></el-select></el-form-item>\n'
        '    </el-form>\n'
        '    <span slot="footer"><el-button @click="visible = false">Cancel</el-button><el-button type="primary" @click="handleSubmit">Save</el-button></span>\n'
        '  </el-dialog>\n</template>\n\n'
        '<script>\nexport default {\n  data() {\n    return { visible: false, form: { name: "", email: "", status: "" } };\n  },\n'
        '  methods: {\n'
        '    open(record) { this.form = { ...record }; this.visible = true; },\n'
        '    handleClose() { /* BUG: form data not reset on close */ },\n'
        '    handleSubmit() { this.$emit("save", this.form); this.visible = false; },\n'
        '  },\n};\n</script>\n'
    )

def create_java_backend_bugfix(d):
    write_file(os.path.join(d, 'pom.xml'),
        '<?xml version="1.0" encoding="UTF-8"?>\n<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
        '  <modelVersion>4.0.0</modelVersion>\n  <groupId>com.example</groupId>\n'
        '  <artifactId>order-service</artifactId><version>1.0.0</version>\n'
        '  <parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>2.7.0</version></parent>\n'
        '  <dependencies>\n'
        '    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-web</artifactId></dependency>\n'
        '    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-test</artifactId><scope>test</scope></dependency>\n'
        '  </dependencies>\n</project>\n'
    )
    write_file(os.path.join(d, 'src', 'main', 'java', 'com', 'example', 'order', 'OrderController.java'),
        'package com.example.order;\n\n'
        'import org.springframework.web.bind.annotation.*;\n'
        'import java.util.*;\nimport java.util.concurrent.*;\n\n'
        '@RestController\n@RequestMapping("/api/orders")\n'
        'public class OrderController {\n\n'
        '    private final Map<String, Object> cache = new ConcurrentHashMap<>();\n'
        '    private int currentPage = 1;  // BUG: shared mutable state\n'
        '    private int pageSize = 10;\n\n'
        '    @GetMapping\n'
        '    public Map<String, Object> listOrders(\n'
        '            @RequestParam(defaultValue = "1") int page,\n'
        '            @RequestParam(defaultValue = "10") int size) {\n'
        '        // BUG: currentPage is shared across concurrent requests\n'
        '        this.currentPage = page;\n'
        '        this.pageSize = size;\n'
        '        Map<String, Object> result = new HashMap<>();\n'
        '        result.put("page", currentPage);\n'
        '        result.put("size", pageSize);\n'
        '        return result;\n'
        '    }\n}\n'
    )

def create_java_data_bugfix(d):
    write_file(os.path.join(d, 'pom.xml'),
        '<?xml version="1.0" encoding="UTF-8"?>\n<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
        '  <modelVersion>4.0.0</modelVersion>\n  <groupId>com.example</groupId>\n'
        '  <artifactId>data-pipeline</artifactId><version>1.0.0</version>\n'
        '  <parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>2.7.0</version></parent>\n'
        '  <dependencies>\n'
        '    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter</artifactId></dependency>\n'
        '  </dependencies>\n</project>\n'
    )
    write_file(os.path.join(d, 'src', 'main', 'java', 'com', 'example', 'pipeline', 'TransformJob.java'),
        'package com.example.pipeline;\n\n'
        'import java.util.*;\n\n'
        'public class TransformJob {\n\n'
        '    public List<Map<String, Object>> transform(List<Map<String, Object>> records) {\n'
        '        List<Map<String, Object>> result = new ArrayList<>();\n'
        '        for (Map<String, Object> record : records) {\n'
        '            Map<String, Object> out = new HashMap<>();\n'
        '            out.put("id", record.get("id"));\n'
        '            out.put("name", record.get("name"));\n'
        '            // BUG: assumes "amount" always exists and is numeric\n'
        '            out.put("amount", ((Number) record.get("amount")).doubleValue());\n'
        '            result.add(out);\n'
        '        }\n'
        '        return result;\n'
        '    }\n}\n'
    )

def create_python_test_bugfix(d):
    write_file(os.path.join(d, 'requirements.txt'),
        'selenium>=4.15.0\npytest>=7.4.0\nwebdriver-manager>=4.0.0\n'
    )
    write_file(os.path.join(d, 'tests', 'test_login.py'),
        'from selenium import webdriver\nfrom selenium.webdriver.common.by import By\n'
        'from selenium.webdriver.support.ui import WebDriverWait\nfrom selenium.webdriver.support import expected_conditions as EC\n\n'
        'class TestLogin:\n'
        '    def setup_method(self):\n'
        '        self.driver = webdriver.Chrome()\n'
        '        self.wait = WebDriverWait(self.driver, 5)\n\n'
        '    def test_login_success(self):\n'
        '        self.driver.get("http://localhost:8080/login")\n'
        '        # BUG: no explicit wait for element, relies on implicit timing\n'
        '        self.driver.find_element(By.ID, "username").send_keys("admin")\n'
        '        self.driver.find_element(By.ID, "password").send_keys("password")\n'
        '        self.driver.find_element(By.ID, "submit").click()\n'
        '        # BUG: assert happens before page loads\n'
        '        assert "Dashboard" in self.driver.title\n\n'
        '    def teardown_method(self):\n'
        '        self.driver.quit()\n'
    )

def create_java_backend_feature(d):
    write_file(os.path.join(d, 'pom.xml'),
        '<?xml version="1.0" encoding="UTF-8"?>\n<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
        '  <modelVersion>4.0.0</modelVersion>\n  <groupId>com.example</groupId>\n'
        '  <artifactId>order-refund</artifactId><version>1.0.0</version>\n'
        '  <parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>2.7.0</version></parent>\n'
        '  <dependencies>\n'
        '    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-web</artifactId></dependency>\n'
        '    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-test</artifactId><scope>test</scope></dependency>\n'
        '  </dependencies>\n</project>\n'
    )
    write_file(os.path.join(d, 'src', 'main', 'java', 'com', 'example', 'order', 'Order.java'),
        'package com.example.order;\n\npublic class Order {\n'
        '    private String orderId;\n    private String status;\n    private double amount;\n'
        '    public String getOrderId() { return orderId; }\n'
        '    public String getStatus() { return status; }\n'
        '    public double getAmount() { return amount; }\n}\n'
    )
    write_file(os.path.join(d, 'src', 'main', 'java', 'com', 'example', 'order', 'OrderController.java'),
        'package com.example.order;\n\n'
        'import org.springframework.web.bind.annotation.*;\n\n'
        '@RestController\n@RequestMapping("/api/orders")\n'
        'public class OrderController {\n'
        '    // TODO: implement refund endpoint\n}\n'
    )

def create_unity_game_bugfix(d):
    write_file(os.path.join(d, 'Assets', 'Scripts', 'EnemyAI.cs'),
        'using UnityEngine;\nusing UnityEngine.AI;\n\n'
        'public class EnemyAI : MonoBehaviour\n{\n'
        '    private NavMeshAgent agent;\n'
        '    private Transform[] patrolPoints;\n'
        '    private int currentPoint = 0;\n\n'
        '    void Start()\n    {\n        agent = GetComponent<NavMeshAgent>();\n    }\n\n'
        '    void Update()\n    {\n'
        '        if (!agent.pathPending && agent.remainingDistance < 0.5f)\n'
        '        {\n'
        '            currentPoint = (currentPoint + 1) % patrolPoints.Length;\n'
        '            agent.SetDestination(patrolPoints[currentPoint].position);\n'
        '            // BUG: no handling for when agent is stuck at corner\n'
        '        }\n'
        '    }\n}\n'
    )

def create_android_bugfix(d):
    write_file(os.path.join(d, 'app', 'src', 'main', 'java', 'com', 'example', 'adapter', 'LoadMoreAdapter.java'),
        'package com.example.adapter;\n\n'
        'import android.view.*;\nimport android.widget.TextView;\nimport androidx.recyclerview.widget.RecyclerView;\nimport java.util.*;\n\n'
        'public class LoadMoreAdapter extends RecyclerView.Adapter<LoadMoreAdapter.ViewHolder> {\n'
        '    private List<String> items = new ArrayList<>();\n'
        '    private boolean isLoading = false;\n\n'
        '    public void addItems(List<String> newItems) {\n'
        '        // BUG: no deduplication, can add same items multiple times\n'
        '        items.addAll(newItems);\n'
        '        notifyDataSetChanged();\n'
        '    }\n\n'
        '    public void onLoadMore() {\n'
        '        if (!isLoading) {\n'
        '            isLoading = true;\n'
        '            // BUG: no debounce, rapid scroll triggers multiple loads\n'
        '            fetchNextPage();\n'
        '        }\n'
        '    }\n\n'
        '    private void fetchNextPage() { /* network call */ }\n\n'
        '    @Override public ViewHolder onCreateViewHolder(ViewGroup p, int v) { return null; }\n'
        '    @Override public void onBindViewHolder(ViewHolder h, int p) { }\n'
        '    @Override public int getItemCount() { return items.size(); }\n\n'
        '    static class ViewHolder extends RecyclerView.ViewHolder {\n'
        '        ViewHolder(View v) { super(v); }\n'
        '    }\n}\n'
    )

def create_html_css_bugfix(d):
    write_file(os.path.join(d, 'index.html'),
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
        '  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '  <title>Activity Landing Page</title>\n  <link rel="stylesheet" href="styles.css">\n</head>\n<body>\n'
        '  <div class="carousel">\n'
        '    <div class="slides">\n'
        '      <div class="slide active"><img src="banner1.jpg" alt="Banner 1"></div>\n'
        '      <div class="slide"><img src="banner2.jpg" alt="Banner 2"></div>\n'
        '      <div class="slide"><img src="banner3.jpg" alt="Banner 3"></div>\n'
        '    </div>\n'
        '    <button class="prev">&lt;</button><button class="next">&gt;</button>\n'
        '  </div>\n'
        '  <div class="cta-section">\n'
        '    <h1>Join Now</h1>\n'
        '    <button class="cta-button">Sign Up</button>\n'
        '  </div>\n'
        '  <script src="script.js"></script>\n</body>\n</html>\n'
    )
    write_file(os.path.join(d, 'styles.css'),
        '.carousel { position: relative; overflow: hidden; width: 100%; height: 400px; }\n'
        '.slides { display: flex; /* BUG: no transition */ }\n'
        '.slide { min-width: 100%; display: none; }\n.slide.active { display: block; }\n'
        '.cta-section { text-align: center; padding: 40px; }\n'
        '.cta-button { /* BUG: no responsive sizing, gets cut off on small screens */\n'
        '  font-size: 18px; padding: 12px 48px; }\n'
    )
    write_file(os.path.join(d, 'script.js'),
        'let current = 0;\nconst slides = document.querySelectorAll(".slide");\n\n'
        'function showSlide(n) {\n'
        '  slides[current].classList.remove("active");\n'
        '  current = (n + slides.length) % slides.length;\n'
        '  slides[current].classList.add("active");\n'
        '  // BUG: no smooth transition, causes flash\n}\n\n'
        'document.querySelector(".next").addEventListener("click", () => showSlide(current + 1));\n'
        'document.querySelector(".prev").addEventListener("click", () => showSlide(current - 1));\n'
    )

def create_js_web_feature(d):
    write_file(os.path.join(d, 'package.json'), json.dumps({
        "name": "batch-import-users",
        "version": "1.0.0",
        "scripts": {"dev": "vue-cli-service serve"},
        "dependencies": {"vue": "^2.7.0", "element-ui": "^2.15.0", "xlsx": "^0.18.0"},
        "devDependencies": {"@vue/cli-service": "^5.0.0"}
    }, indent=2))
    write_file(os.path.join(d, 'src', 'UserManagement.vue'),
        '<template>\n  <div>\n'
        '    <el-table :data="users"><el-table-column prop="name" label="Name" /><el-table-column prop="email" label="Email" /></el-table>\n'
        '    <el-button @click="showImport = true">Batch Import</el-button>\n'
        '    <!-- TODO: implement batch import dialog -->\n'
        '  </div>\n</template>\n\n'
        '<script>\nexport default {\n  data() { return { users: [], showImport: false }; },\n'
        '  methods: {\n    // TODO: implement Excel parsing and batch import\n  },\n};\n</script>\n'
    )

def create_c_backend_bugfix(d):
    write_file(os.path.join(d, 'Makefile'),
        'CC = gcc\nCFLAGS = -Wall -g -O2\nTARGET = gateway\n\nall: $(TARGET)\n\n$(TARGET): main.o\n\t$(CC) -o $@ $^\n\nclean:\n\trm -f $(TARGET) *.o\n'
    )
    write_file(os.path.join(d, 'main.c'),
        '#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n\n'
        'typedef struct {\n    char *key;\n    char *value;\n} ConfigEntry;\n\n'
        'typedef struct {\n    ConfigEntry *entries;\n    int count;\n    int capacity;\n} ConfigStore;\n\n'
        'void config_init(ConfigStore *store) {\n    store->entries = NULL; store->count = 0; store->capacity = 0;\n}\n\n'
        'void config_set(ConfigStore *store, const char *key, const char *value) {\n'
        '    // BUG: memory leak - old value not freed when overwriting\n'
        '    // BUG: key not copied, just pointer assigned\n'
        '    if (store->count >= store->capacity) {\n'
        '        store->capacity = store->capacity ? store->capacity * 2 : 16;\n'
        '        store->entries = realloc(store->entries, store->capacity * sizeof(ConfigEntry));\n'
        '    }\n'
        '    store->entries[store->count].key = (char *)key;\n'
        '    store->entries[store->count].value = strdup(value);\n'
        '    store->count++;\n}\n\n'
        'int main() {\n    ConfigStore store; config_init(&store);\n'
        '    while (1) { config_set(&store, "heartbeat", "alive"); /* simulate running */ }\n'
        '    return 0;\n}\n'
    )

def create_python_db_bugfix(d):
    write_file(os.path.join(d, 'requirements.txt'),
        'pymongo>=4.6.0\npython-dotenv>=1.0.0\n'
    )
    write_file(os.path.join(d, 'queries.py'),
        'from pymongo import MongoClient\nfrom datetime import datetime, timedelta\n\n'
        'client = MongoClient("mongodb://localhost:27017")\ndb = client["analytics"]\n\n'
        'def get_user_stats(user_id: str, start_date: datetime, end_date: datetime):\n'
        '    # BUG: no index on created_at, slow aggregation\n'
        '    pipeline = [\n'
        '        {"$match": {"user_id": user_id, "created_at": {"$gte": start_date, "$lte": end_date}}},\n'
        '        {"$group": {"_id": "$category", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},\n'
        '        {"$sort": {"total": -1}},\n'
        '        # BUG: missing $limit stage, processes all data\n'
        '    ]\n'
        '    return list(db.transactions.aggregate(pipeline))\n'
    )

def create_go_backend_bugfix(d):
    write_file(os.path.join(d, 'go.mod'),
        'module grpc-timeout-demo\n\ngo 1.21\n\nrequire (\n\tgoogle.golang.org/grpc v1.60.0\n)\n'
    )
    write_file(os.path.join(d, 'main.go'),
        'package main\n\nimport (\n\t"context"\n\t"fmt"\n\t"time"\n\n\t"google.golang.org/grpc"\n)\n\n'
        'func callService(ctx context.Context) error {\n'
        '\t// BUG: client timeout shorter than server processing time\n'
        '\tclientCtx, cancel := context.WithTimeout(ctx, 2*time.Second)\n'
        '\tdefer cancel()\n\n'
        '\tconn, _ := grpc.Dial("localhost:50051", grpc.WithInsecure())\n'
        '\tdefer conn.Close()\n\n'
        '\t// Server takes 3-5s to process, but client times out at 2s\n'
        '\t// Server still completes and logs success, but client already returned error\n'
        '\t_ = clientCtx\n\treturn fmt.Errorf("context deadline exceeded")\n}\n\n'
        'func main() {\n\tcallService(context.Background())\n}\n'
    )

def create_python_backend_bugfix(d):
    write_file(os.path.join(d, 'requirements.txt'),
        'fastapi>=0.104.0\nuvicorn>=0.24.0\npydantic>=2.5.0\n'
    )
    write_file(os.path.join(d, 'app', 'main.py'),
        'from fastapi import FastAPI, HTTPException\nfrom pydantic import BaseModel\n\napp = FastAPI()\n\n'
        'class SearchRequest(BaseModel):\n    keyword: str\n    category: str = ""\n\n'
        '@app.post("/api/search")\nasync def search(req: SearchRequest):\n'
        '    # BUG: no encoding handling for Chinese characters\n'
        '    # BUG: special characters cause 500 errors\n'
        '    keyword = req.keyword\n'
        '    result = do_search(keyword)\n'
        '    return {"results": result}\n\n'
        'def do_search(keyword: str):\n'
        '    # BUG: no input sanitization\n'
        '    return [{"id": 1, "name": f"Result for {keyword}"}]\n'
    )

def create_python_data_feature(d):
    write_file(os.path.join(d, 'requirements.txt'),
        'fastapi>=0.104.0\nnetworkx>=3.2.0\npydantic>=2.5.0\n'
    )
    write_file(os.path.join(d, 'app', 'main.py'),
        'from fastapi import FastAPI\n\napp = FastAPI()\n\n'
        '# TODO: implement data lineage tracking\n'
        '# - Parse SQL/dataflow to extract dependencies\n'
        '# - Build dependency graph\n'
        '# - Provide visualization API\n'
        '# - Support upstream/downstream queries\n'
    )

def create_python_ml_refactor(d):
    write_file(os.path.join(d, 'requirements.txt'),
        'torch>=2.1.0\nnumpy>=1.24.0\nmatplotlib>=3.8.0\n'
    )
    write_file(os.path.join(d, 'train.py'),
        'import torch\nimport torch.nn as nn\nimport torch.optim as optim\nfrom torch.utils.data import DataLoader, TensorDataset\nimport numpy as np\n\n'
        '# All-in-one training script - needs refactoring\n\n'
        'class SimpleModel(nn.Module):\n'
        '    def __init__(self, input_dim=784, hidden_dim=256, output_dim=10):\n'
        '        super().__init__()\n'
        '        self.fc1 = nn.Linear(input_dim, hidden_dim)\n'
        '        self.fc2 = nn.Linear(hidden_dim, output_dim)\n'
        '    def forward(self, x):\n'
        '        x = torch.relu(self.fc1(x))\n'
        '        return self.fc2(x)\n\n'
        'def train():\n'
        '    # Data loading mixed with training logic\n'
        '    data = np.random.randn(1000, 784).astype(np.float32)\n'
        '    labels = np.random.randint(0, 10, 1000)\n'
        '    dataset = TensorDataset(torch.from_numpy(data), torch.from_numpy(labels))\n'
        '    loader = DataLoader(dataset, batch_size=32, shuffle=True)\n\n'
        '    model = SimpleModel()\n'
        '    optimizer = optim.Adam(model.parameters(), lr=0.001)\n'
        '    criterion = nn.CrossEntropyLoss()\n\n'
        '    for epoch in range(10):\n'
        '        for batch_x, batch_y in loader:\n'
        '            optimizer.zero_grad()\n'
        '            output = model(batch_x)\n'
        '            loss = criterion(output, batch_y)\n'
        '            loss.backward()\n'
        '            optimizer.step()\n'
        '        print(f"Epoch {epoch}, Loss: {loss.item():.4f}")\n\n'
        'if __name__ == "__main__":\n    train()\n'
    )

def create_python_etl_bugfix(d):
    write_file(os.path.join(d, 'requirements.txt'),
        'pandas>=2.1.0\npyarrow>=14.0.0\n'
    )
    write_file(os.path.join(d, 'etl', 'transform.py'),
        'import pandas as pd\nfrom typing import List, Dict, Any\n\n'
        'def transform_records(records: List[Dict[str, Any]]) -> pd.DataFrame:\n'
        '    df = pd.DataFrame(records)\n'
        '    # BUG: assumes all expected columns exist\n'
        '    df["total"] = df["price"] * df["quantity"]\n'
        '    # BUG: no handling for new unexpected columns\n'
        '    df = df[["id", "name", "total"]]\n'
        '    return df\n'
    )

def create_ts_web_feature(d):
    write_file(os.path.join(d, 'package.json'), json.dumps({
        "name": "kanban-drag-drop",
        "version": "1.0.0",
        "scripts": {"dev": "vite", "build": "tsc && vite build"},
        "dependencies": {"react": "^18.2.0", "antd": "^5.12.0"},
        "devDependencies": {"typescript": "^5.3.0", "vite": "^5.0.0", "@types/react": "^18.2.0"}
    }, indent=2))
    write_file(os.path.join(d, 'src', 'KanbanBoard.tsx'),
        'import React, { useState } from "react";\n\n'
        'interface Card {\n  id: string;\n  title: string;\n  status: "todo" | "doing" | "done";\n}\n\n'
        'const KanbanBoard: React.FC = () => {\n'
        '  const [cards, setCards] = useState<Card[]>([]);\n'
        '  // TODO: implement drag and drop between columns\n'
        '  // TODO: implement status auto-update on drop\n'
        '  return <div>Kanban Board - TODO: implement</div>;\n'
        '};\n\nexport default KanbanBoard;\n'
    )

def create_python_ai_bugfix(d):
    write_file(os.path.join(d, 'requirements.txt'),
        'torch>=2.1.0\ntransformers>=4.36.0\npsutil>=5.9.0\n'
    )
    write_file(os.path.join(d, 'inference.py'),
        'import torch\nfrom transformers import AutoModelForCausalLM, AutoTokenizer\n\n'
        'class InferenceService:\n'
        '    def __init__(self, model_name: str):\n'
        '        self.tokenizer = AutoTokenizer.from_pretrained(model_name)\n'
        '        self.model = AutoModelForCausalLM.from_pretrained(model_name)\n'
        '        self.model.eval()\n\n'
        '    def generate(self, prompt: str, max_new_tokens: int = 100) -> str:\n'
        '        inputs = self.tokenizer(prompt, return_tensors="pt")\n'
        '        # BUG: tensors not moved to correct device after inference\n'
        '        with torch.no_grad():\n'
        '            outputs = self.model.generate(**inputs, max_new_tokens=max_new_tokens)\n'
        '        # BUG: intermediate tensors not explicitly deleted\n'
        '        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)\n\n'
        '    def batch_generate(self, prompts: list, max_new_tokens: int = 100) -> list:\n'
        '        results = []\n'
        '        for prompt in prompts:\n'
        '            results.append(self.generate(prompt, max_new_tokens))\n'
        '            # BUG: GPU memory accumulates across batch items\n'
        '        return results\n'
    )

def create_rn_explain(d):
    write_file(os.path.join(d, 'package.json'), json.dumps({
        "name": "rn-nav-explain",
        "version": "1.0.0",
        "dependencies": {
            "react-native": "^0.73.0",
            "@react-navigation/native": "^6.1.0",
            "@react-navigation/stack": "^6.3.0",
            "@react-navigation/bottom-tabs": "^6.5.0"
        }
    }, indent=2))
    write_file(os.path.join(d, 'src', 'navigation', 'AppNavigator.tsx'),
        'import React from "react";\n'
        'import { NavigationContainer } from "@react-navigation/native";\n'
        'import { createStackNavigator } from "@react-navigation/stack";\n'
        'import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";\n\n'
        'const Stack = createStackNavigator();\nconst Tab = createBottomTabNavigator();\n\n'
        'function HomeStack() {\n'
        '  return (\n'
        '    <Stack.Navigator>\n'
        '      <Stack.Screen name="Home" component={HomeScreen} />\n'
        '      <Stack.Screen name="Detail" component={DetailScreen} />\n'
        '      <Stack.Screen name="Settings" component={SettingsScreen} />\n'
        '    </Stack.Navigator>\n'
        '  );\n}\n\n'
        'export default function AppNavigator() {\n'
        '  return (\n'
        '    <NavigationContainer>\n'
        '      <Tab.Navigator>\n'
        '        <Tab.Screen name="HomeTab" component={HomeStack} />\n'
        '        <Tab.Screen name="ProfileTab" component={ProfileStack} />\n'
        '      </Tab.Navigator>\n'
        '    </NavigationContainer>\n'
        '  );\n}\n'
    )

def create_python_devops_feature(d):
    write_file(os.path.join(d, 'requirements.txt'),
        'fastapi>=0.104.0\napscheduler>=3.10.0\nhttpx>=0.25.0\npydantic>=2.5.0\n'
    )
    write_file(os.path.join(d, 'app', 'main.py'),
        'from fastapi import FastAPI\n\napp = FastAPI()\n\n'
        '# TODO: implement auto patrol feature\n'
        '# - Scheduled health checks for services\n'
        '# - Alert to DingTalk on failure\n'
        '# - Configurable check rules\n'
        '# - Alert dedup and aggregation\n'
    )

def create_miniprogram_feature(d):
    write_file(os.path.join(d, 'app.json'),
        '{\n  "pages": [\n    "pages/index/index",\n    "pages/checkin/checkin",\n    "pages/profile/profile"\n  ],\n'
        '  "window": {\n    "navigationBarTitleText": "Mini App"\n  }\n}\n'
    )
    write_file(os.path.join(d, 'pages', 'checkin', 'checkin.wxml'),
        '<view class="container">\n'
        '  <text class="title">Daily Check-in</text>\n'
        '  <button bindtap="handleCheckIn">Check In</button>\n'
        '  <!-- TODO: implement check-in logic and reward display -->\n'
        '</view>\n'
    )
    write_file(os.path.join(d, 'pages', 'checkin', 'checkin.js'),
        'Page({\n  data: { checkedIn: false, streak: 0 },\n'
        '  handleCheckIn() {\n    // TODO: implement check-in with date validation\n  },\n});\n'
    )

def create_java_test_quality(d):
    write_file(os.path.join(d, 'pom.xml'),
        '<?xml version="1.0" encoding="UTF-8"?>\n<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
        '  <modelVersion>4.0.0</modelVersion>\n  <groupId>com.example</groupId>\n'
        '  <artifactId>order-service-test</artifactId><version>1.0.0</version>\n'
        '  <parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>2.7.0</version></parent>\n'
        '  <dependencies>\n'
        '    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-web</artifactId></dependency>\n'
        '    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-test</artifactId><scope>test</scope></dependency>\n'
        '    <dependency><groupId>org.mockito</groupId><artifactId>mockito-core</artifactId><scope>test</scope></dependency>\n'
        '  </dependencies>\n</project>\n'
    )
    write_file(os.path.join(d, 'src', 'main', 'java', 'com', 'example', 'order', 'OrderService.java'),
        'package com.example.order;\n\n'
        'import org.springframework.stereotype.Service;\nimport java.util.*;\n\n'
        '@Service\npublic class OrderService {\n\n'
        '    public Order createOrder(OrderRequest req) {\n'
        '        if (req.getItems() == null || req.getItems().isEmpty()) throw new IllegalArgumentException("Empty order");\n'
        '        if (req.getUserId() == null) throw new IllegalArgumentException("No user");\n'
        '        return new Order(UUID.randomUUID().toString(), req.getUserId(), "CREATED", calculateTotal(req));\n'
        '    }\n\n'
        '    public Order cancelOrder(String orderId) {\n'
        '        Order order = findOrder(orderId);\n'
        '        if ("SHIPPED".equals(order.getStatus())) throw new IllegalStateException("Cannot cancel shipped order");\n'
        '        order.setStatus("CANCELLED");\n'
        '        return order;\n'
        '    }\n\n'
        '    private double calculateTotal(OrderRequest req) { return 0.0; }\n'
        '    private Order findOrder(String id) { return new Order(id, "user1", "CREATED", 0.0); }\n}\n'
    )
    write_file(os.path.join(d, 'src', 'test', 'java', 'com', 'example', 'order', 'OrderServiceTest.java'),
        'package com.example.order;\n\n'
        'import org.junit.jupiter.api.Test;\nimport static org.junit.jupiter.api.Assertions.*;\n\n'
        'class OrderServiceTest {\n'
        '    // TODO: add comprehensive tests - current coverage is only ~30%\n'
        '    @Test void testCreateOrder() { /* placeholder */ }\n}\n'
    )

def create_lua_game_bugfix(d):
    write_file(os.path.join(d, 'scripts', 'skill_system.lua'),
        'local SkillSystem = {}\nSkillSystem.__index = SkillSystem\n\n'
        'function SkillSystem:new()\n'
        '    local obj = { cooldowns = {}, active_effects = {} }\n'
        '    setmetatable(obj, self)\n    return obj\nend\n\n'
        'function SkillSystem:cast_skill(caster, skill_id, target)\n'
        '    local skill = self.skills[skill_id]\n'
        '    if not skill then return false end\n\n'
        '    -- Apply damage\n'
        '    self:apply_damage(caster, target, skill.base_damage)\n\n'
        '    -- Apply effect\n'
        '    if skill.effect then\n'
        '        self:apply_effect(target, skill.effect)\n'
        '    end\n\n'
        '    -- BUG: damage event fires twice when effect also deals damage\n'
        '    if skill.effect and skill.effect.type == "damage" then\n'
        '        self:apply_damage(caster, target, skill.effect.value)\n'
        '    end\n\n'
        '    return true\nend\n\n'
        'function SkillSystem:apply_damage(caster, target, amount)\n'
        '    target.hp = target.hp - amount\n'
        '    -- trigger event\n'
        '    self:on_damage_dealt(caster, target, amount)\nend\n\n'
        'return SkillSystem\n'
    )

def create_python_data_explain(d):
    write_file(os.path.join(d, 'requirements.txt'),
        'pandas>=2.1.0\nsqlalchemy>=2.0.0\n'
    )
    write_file(os.path.join(d, 'analytics', 'retention.py'),
        'import pandas as pd\nfrom sqlalchemy import create_engine\n\n'
        'engine = create_engine("postgresql://localhost/analytics")\n\n'
        'def calculate_retention(cohort_date: str, period: int = 7) -> pd.DataFrame:\n'
        '    query = """\n'
        '    WITH cohort AS (\n'
        '        SELECT user_id, MIN(DATE(created_at)) as first_day\n'
        '        FROM events WHERE DATE(created_at) = %s\n'
        '        GROUP BY user_id\n'
        '    ),\n'
        '    activity AS (\n'
        '        SELECT c.user_id, DATE(e.created_at) as active_date,\n'
        '               DATEDIFF(DATE(e.created_at), c.first_day) as day_n\n'
        '        FROM cohort c\n'
        '        JOIN events e ON c.user_id = e.user_id\n'
        '    )\n'
        '    SELECT day_n, COUNT(DISTINCT user_id) as retained_users,\n'
        '           COUNT(DISTINCT user_id) * 1.0 / (SELECT COUNT(*) FROM cohort) as retention_rate\n'
        '    FROM activity WHERE day_n <= %s\n'
        '    GROUP BY day_n ORDER BY day_n\n'
        '    """\n'
        '    # BUG: retention calculation may be incorrect - needs review\n'
        '    return pd.read_sql(query, engine, params=[cohort_date, period])\n'
    )

def create_java_explain(d):
    write_file(os.path.join(d, 'pom.xml'),
        '<?xml version="1.0" encoding="UTF-8"?>\n<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
        '  <modelVersion>4.0.0</modelVersion>\n  <groupId>com.example</groupId>\n'
        '  <artifactId>rbac-system</artifactId><version>1.0.0</version>\n'
        '  <parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>2.7.0</version></parent>\n'
        '  <dependencies>\n'
        '    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-web</artifactId></dependency>\n'
        '    <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-security</artifactId></dependency>\n'
        '  </dependencies>\n</project>\n'
    )
    write_file(os.path.join(d, 'src', 'main', 'java', 'com', 'example', 'security', 'RbacService.java'),
        'package com.example.security;\n\n'
        'import org.springframework.security.core.*;\nimport org.springframework.security.access.annotation.*;\n'
        'import java.util.*;\n\n'
        '@Service\npublic class RbacService {\n\n'
        '    private Map<String, Set<String>> rolePermissions = new HashMap<>();\n'
        '    private Map<String, Set<String>> userRoles = new HashMap<>();\n\n'
        '    public boolean hasPermission(String userId, String permission) {\n'
        '        Set<String> roles = userRoles.getOrDefault(userId, Collections.emptySet());\n'
        '        for (String role : roles) {\n'
        '            Set<String> perms = rolePermissions.getOrDefault(role, Collections.emptySet());\n'
        '            if (perms.contains(permission)) return true;\n'
        '            // Check parent roles recursively\n'
        '            if (checkParentRoles(role, permission)) return true;\n'
        '        }\n'
        '        return false;\n'
        '    }\n\n'
        '    private boolean checkParentRoles(String role, String permission) {\n'
        '        // Complex inheritance logic - needs explanation\n'
        '        return false;\n'
        '    }\n}\n'
    )

def create_html_css_feature(d):
    write_file(os.path.join(d, 'index.html'),
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
        '  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '  <title>Product Comparison</title>\n  <link rel="stylesheet" href="styles.css">\n</head>\n<body>\n'
        '  <section class="products">\n'
        '    <div class="product-card" data-id="1"><h3>Product A</h3><p>Basic plan</p></div>\n'
        '    <div class="product-card" data-id="2"><h3>Product B</h3><p>Pro plan</p></div>\n'
        '    <div class="product-card" data-id="3"><h3>Product C</h3><p>Enterprise plan</p></div>\n'
        '  </section>\n'
        '  <div id="compare-area"><!-- TODO: comparison panel --></div>\n'
        '  <script src="script.js"></script>\n</body>\n</html>\n'
    )
    write_file(os.path.join(d, 'styles.css'),
        '.products { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; padding: 40px; }\n'
        '.product-card { border: 1px solid #ddd; border-radius: 8px; padding: 24px; cursor: pointer; }\n'
        '.product-card.selected { border-color: #1890ff; box-shadow: 0 0 0 2px rgba(24,144,255,0.2); }\n'
        '#compare-area { /* TODO: comparison layout */ }\n'
    )
    write_file(os.path.join(d, 'script.js'),
        '// TODO: implement product comparison feature\n'
        '// - Select products to compare\n'
        '// - Show side-by-side comparison\n'
        '// - Highlight differences\n'
    )

def create_shell_cicd(d):
    write_file(os.path.join(d, 'Jenkinsfile'),
        'pipeline {\n  agent any\n  stages {\n'
        '    stage("Install") {\n      steps {\n        sh "npm install"\n      }\n'
        '    }\n    stage("Build") {\n      steps {\n        sh "npm run build"\n      }\n'
        '    }\n    stage("Test") {\n      steps {\n        sh "npm test"\n      }\n'
        '    }\n  }\n}\n'
    )
    write_file(os.path.join(d, '.npmrc'), '')
    write_file(os.path.join(d, 'build.sh'),
        '#!/bin/bash\nset -e\n\n'
        '# BUG: no cache configuration\n'
        '# BUG: no mirror source for dependencies\n'
        'echo "Installing dependencies..."\nnpm install\n\n'
        'echo "Building..."\nnpm run build\n\n'
        'echo "Running tests..."\nnpm test\n'
    )

def create_python_ai_feature(d):
    write_file(os.path.join(d, 'requirements.txt'),
        'fastapi>=0.104.0\nuvicorn>=0.24.0\npydantic>=2.5.0\nhttpx>=0.25.0\n'
    )
    write_file(os.path.join(d, 'app', 'main.py'),
        'from fastapi import FastAPI\nfrom pydantic import BaseModel\n\napp = FastAPI()\n\n'
        'class ABTestConfig(BaseModel):\n    name: str\n    variants: list\n    traffic_ratio: list\n\n'
        '# TODO: implement A/B test routing feature\n'
        '# - Route requests to different model versions by ratio\n'
        '# - Collect and compare results automatically\n'
        '# - Support dynamic ratio adjustment\n'
    )


QUESTIONS = [
    ('l1-001', 'wrr-table-filter-paging', 'bug-fix', 'web_frontend', 'ts'),
    ('l1-002', 'wrr-flutter-refresh-jump', 'bug-fix', 'mobile_app', 'other'),
    ('l1-003', 'wrr-vue-form-stale', 'bug-fix', 'web_frontend', 'js'),
    ('l1-004', 'wrr-order-concurrent-dup', 'bug-fix', 'backend_service', 'java'),
    ('l1-005', 'wrr-pipeline-keyerror', 'bug-fix', 'data_engineering', 'java'),
    ('l1-006', 'wrr-selenium-ci-flaky', 'bug-fix', 'devtools_test', 'python'),
    ('l1-007', 'wrr-refund-api', 'feature', 'backend_service', 'java'),
    ('l1-008', 'wrr-unity-nav-stuck', 'bug-fix', 'game_dev', 'other'),
    ('l1-009', 'wrr-rv-duplicate-load', 'bug-fix', 'mobile_app', 'java'),
    ('l1-010', 'wrr-carousel-mobile-css', 'bug-fix', 'web_frontend', 'html/css'),
    ('l1-011', 'wrr-batch-import-users', 'feature', 'web_frontend', 'js'),
    ('l1-012', 'wrr-c-gateway-memleak', 'bug-fix', 'backend_service', 'c'),
    ('l1-013', 'wrr-mongo-slow-query', 'bug-fix', 'database_storage', 'python'),
    ('l1-014', 'wrr-grpc-timeout-mismatch', 'bug-fix', 'backend_service', 'go'),
    ('l1-015', 'wrr-fastapi-encoding', 'bug-fix', 'backend_service', 'python'),
    ('l1-016', 'wrr-data-lineage-trace', 'feature', 'data_engineering', 'python'),
    ('l1-017', 'wrr-ml-train-refactor', 'refactor-maintenance', 'ai_ml', 'python'),
    ('l1-018', 'wrr-etl-schema-drift', 'bug-fix', 'data_engineering', 'python'),
    ('l1-019', 'wrr-kanban-drag-drop', 'feature', 'web_frontend', 'ts'),
    ('l1-020', 'wrr-infer-gpu-leak', 'bug-fix', 'ai_ml', 'python'),
    ('l1-021', 'wrr-rn-nav-explain', 'code-explanation', 'mobile_app', 'other'),
    ('l1-022', 'wrr-auto-patrol-alert', 'feature', 'devops_infrastructure', 'python'),
    ('l1-023', 'wrr-checkin-reward', 'feature', 'mobile_app', 'other'),
    ('l1-024', 'wrr-order-test-coverage', 'testing-quality', 'backend_service', 'java'),
    ('l1-025', 'wrr-lua-skill-dmg-bug', 'bug-fix', 'game_dev', 'lua'),
    ('l1-026', 'wrr-retention-calc-explain', 'code-explanation', 'data_engineering', 'python'),
    ('l1-027', 'wrr-java-rbac-explain', 'code-explanation', 'backend_service', 'java'),
    ('l1-028', 'wrr-product-compare', 'feature', 'web_frontend', 'html/css'),
    ('l1-029', 'wrr-cicd-cache-mirror', 'build-release-config', 'devops_infrastructure', 'shell'),
    ('l1-030', 'wrr-ab-test-routing', 'feature', 'ai_ml', 'python'),
]

QUERIES = {
    'l1-001': '我们这个 React + TypeScript 的后台管理系统，用户反馈表格组件在筛选条件变化后，分页会跳回第一页，但表格数据没刷新，还是显示上一次筛选的结果。只有手动点一下分页才会更新。你帮我排查下这个 bug，改掉它。项目用的 antd 的 Table 组件，数据走的 useRequest 请求。',
    'l1-002': 'Flutter App 里有个列表页，用户说下拉刷新之后数据确实更新了，但列表滚动位置会随机跳动，有时候还会闪一下白屏。你帮我看看是什么问题，修一下。',
    'l1-003': '前端项目用的 Vue2 + Element UI，有个表单弹窗，点编辑打开后修改字段，关闭再打开另一个记录，里面还是上一次的数据。只有刷新页面才会好。帮我查下这个 bug。',
    'l1-004': 'Spring Boot 项目里有个订单查询接口，并发一高就返回重复数据，分页也乱掉了。本地单测没问题，压测才复现。帮我查下原因修一下。',
    'l1-005': '数据管道跑着跑着就报 KeyError 了，日志看是上游数据格式变了多了几个字段。帮我看下 transform 逻辑哪里没兼容好，顺便加个字段校验。',
    'l1-006': '我们 Selenium 测试套件跑 CI 的时候经常莫名失败，本地跑就没问题。看日志是元素找不到或者超时，但页面明明加载出来了。帮我排查下，改稳定点。',
    'l1-007': '帮我在订单服务里加一个退款接口，需要校验订单状态是已支付且未发货才能退，调用支付中心的退款API，成功后更新订单状态。',
    'l1-008': 'Unity 游戏里有个怪物AI，巡逻的时候偶尔会卡在墙角出不来，然后就在那原地转圈。帮我看看寻路逻辑哪里有问题。',
    'l1-009': 'Android 项目里有个 RecyclerView 列表，滑到底部加载更多的时候偶尔会重复插入相同数据，导致列表出现重复项。帮我查下这个 bug。',
    'l1-010': '这个活动落地页在手机上打开，轮播图有时候会闪一下，而且底部按钮在小屏上被截掉了。帮我修一下样式问题。',
    'l1-011': '帮我在现有的用户管理页面加个批量导入功能，支持上传 Excel 文件，解析后批量创建用户，重复的跳过并在结果里标注出来。',
    'l1-012': 'C 语言写的嵌入式网关程序，运行几天后内存占用持续增长，最终OOM被杀。帮我排查下内存泄漏在哪里。',
    'l1-013': 'MongoDB 的查询最近变慢了，有个聚合管道跑了好几秒，数据量也不算大。帮我看看索引和查询有没有优化空间。',
    'l1-014': 'Go 写的微服务，有个 gRPC 接口偶尔返回 context deadline exceeded，客户端超时了但服务端日志显示处理成功了。帮我查下这个不一致的问题。',
    'l1-015': 'FastAPI 项目里有个接口，请求参数里带中文的时候偶尔会乱码，而且有些特殊字符直接500了。帮我修一下。',
    'l1-016': '帮我在数据平台加个数据血缘追踪功能，能查看某个表的上下游依赖关系，支持可视化展示。',
    'l1-017': '这个训练脚本太乱了，模型定义、数据加载、训练循环全写在一个文件里，帮我拆分一下，按模块整理好，保持训练效果不变。',
    'l1-018': 'ETL 跑到一半报错 KeyError，看日志是上游数据格式变了多了几个字段，帮我看下 transform 逻辑哪里没兼容好，顺便加个字段校验。',
    'l1-019': '帮我在现有的 React 管理后台加个可拖拽的看板功能，类似 Trello 那种，支持列之间拖动卡片，状态自动更新。',
    'l1-020': '模型推理服务最近经常 OOM，看监控是显存没释放干净，推理完一批之后显存没回到基线。帮我查下哪里泄漏了。',
    'l1-021': '这个 RN 项目我不太熟，帮我看下导航那块代码是怎么组织的，特别是深层嵌套页面的传参逻辑，给我梳理一下。',
    'l1-022': '帮我在运维平台加个自动巡检功能，定时检查各服务健康状态，异常自动发告警到钉钉群。',
    'l1-023': '帮我在小程序里加个签到打卡功能，每天只能签一次，连续签到有奖励提示，签到记录能在个人中心查看。',
    'l1-024': '帮我把订单服务核心接口的单元测试补齐，现在覆盖率才30%多，太低了。重点覆盖异常分支。',
    'l1-025': '游戏里有个 Lua 脚本控制的技能系统，释放技能后偶尔伤害计算不对，有时候会多算一次。帮我查下这个 bug。',
    'l1-026': '帮我看下这个数仓的 SQL 逻辑，特别是那个留存率的计算，总觉得算出来的数不太对，帮我理清楚。',
    'l1-027': '这个 Java 项目的权限模块我看不太懂，RBAC 那块代码绕来绕去的，帮我梳理下整体架构和调用链路。',
    'l1-028': '帮我在官网首页加个产品对比功能，用户可以勾选几个产品然后并排对比参数，要好看一点。',
    'l1-029': 'CI/CD 流水线最近构建老失败，看日志是依赖下载超时。帮我改下构建脚本，加上缓存和镜像源配置。',
    'l1-030': '帮我在模型服务里加个 A/B 测试功能，能按比例分流请求到不同模型版本，结果自动统计对比。',
}

for qid, folder, task_type, app_domain, language in QUESTIONS:
    query = QUERIES[qid]
    create_skeleton(folder, task_type, app_domain, language, query, qid)
    print("Created skeleton: %s" % folder)

print("\nAll 30 project skeletons created!")
