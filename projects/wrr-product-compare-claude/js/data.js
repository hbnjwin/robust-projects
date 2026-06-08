export const CATEGORIES = {
  'cloud-server': {
    name: '云服务器',
    paramGroups: [
      {
        groupId: 'basic',
        groupName: '基本信息',
        params: [
          { paramId: 'region', paramName: '可用区域', type: 'text' },
          { paramId: 'os_support', paramName: '操作系统', type: 'text' },
          { paramId: 'cpu', paramName: 'CPU核数', unit: '核', type: 'number' },
          { paramId: 'memory', paramName: '内存', unit: 'GB', type: 'number' },
          { paramId: 'instance_type', paramName: '实例类型', type: 'text' },
          { paramId: 'deployment_mode', paramName: '部署模式', type: 'text' },
          { paramId: 'min_purchase', paramName: '最低购买时长', type: 'text' },
          { paramId: 'billing_model', paramName: '计费方式', type: 'text' }
        ]
      },
      {
        groupId: 'compute',
        groupName: '计算性能',
        params: [
          { paramId: 'cpu_arch', paramName: 'CPU架构', type: 'text' },
          { paramId: 'cpu_frequency', paramName: 'CPU主频', unit: 'GHz', type: 'number' },
          { paramId: 'cpu_benchmark', paramName: '性能基准分', type: 'number' },
          { paramId: 'gpu_support', paramName: 'GPU支持', type: 'boolean' },
          { paramId: 'gpu_model', paramName: 'GPU型号', type: 'text' },
          { paramId: 'burst_capability', paramName: '突发性能', type: 'boolean' }
        ]
      },
      {
        groupId: 'storage',
        groupName: '存储配置',
        params: [
          { paramId: 'system_disk_type', paramName: '系统盘类型', type: 'text' },
          { paramId: 'system_disk_size', paramName: '系统盘容量', unit: 'GB', type: 'number' },
          { paramId: 'data_disk_type', paramName: '数据盘类型', type: 'text' },
          { paramId: 'data_disk_max', paramName: '数据盘最大容量', unit: 'TB', type: 'number' },
          { paramId: 'iops', paramName: 'IOPS', type: 'number' }
        ]
      },
      {
        groupId: 'network',
        groupName: '网络配置',
        params: [
          { paramId: 'bandwidth_max', paramName: '最大带宽', unit: 'Gbps', type: 'number' },
          { paramId: 'ip_count', paramName: '公网IP数量', type: 'number' },
          { paramId: 'vpc_support', paramName: 'VPC支持', type: 'boolean' },
          { paramId: 'ipv6', paramName: 'IPv6支持', type: 'boolean' },
          { paramId: 'load_balancer', paramName: '负载均衡', type: 'boolean' }
        ]
      },
      {
        groupId: 'security',
        groupName: '安全功能',
        params: [
          { paramId: 'ddos_protection', paramName: 'DDoS防护', type: 'boolean' },
          { paramId: 'firewall', paramName: '云防火墙', type: 'boolean' },
          { paramId: 'encryption', paramName: '数据加密', type: 'text' },
          { paramId: 'compliance', paramName: '合规认证', type: 'text' }
        ]
      },
      {
        groupId: 'service',
        groupName: '服务支持',
        params: [
          { paramId: 'sla', paramName: 'SLA可用性', type: 'text' },
          { paramId: 'support_level', paramName: '技术支持', type: 'text' },
          { paramId: 'backup', paramName: '自动备份', type: 'text' },
          { paramId: 'monitoring', paramName: '监控告警', type: 'boolean' },
          { paramId: 'api_access', paramName: 'API接口', type: 'boolean' }
        ]
      }
    ]
  },
  'object-storage': {
    name: '对象存储',
    paramGroups: [
      {
        groupId: 'basic',
        groupName: '基本信息',
        params: [
          { paramId: 'region', paramName: '可用区域', type: 'text' },
          { paramId: 'storage_class', paramName: '存储类型', type: 'text' },
          { paramId: 'min_purchase', paramName: '最低购买时长', type: 'text' },
          { paramId: 'billing_model', paramName: '计费方式', type: 'text' },
          { paramId: 'free_tier', paramName: '免费额度', type: 'text' }
        ]
      },
      {
        groupId: 'capacity',
        groupName: '存储能力',
        params: [
          { paramId: 'max_object_size', paramName: '单文件最大', unit: 'TB', type: 'number' },
          { paramId: 'max_bucket_count', paramName: '最大存储桶数', type: 'number' },
          { paramId: 'versioning', paramName: '版本管理', type: 'boolean' },
          { paramId: 'lifecycle', paramName: '生命周期管理', type: 'boolean' },
          { paramId: 'replication', paramName: '跨区域复制', type: 'boolean' },
          { paramId: 'storage_limit', paramName: '存储上限', type: 'text' }
        ]
      },
      {
        groupId: 'data-mgmt',
        groupName: '数据管理',
        params: [
          { paramId: 'search', paramName: '数据检索', type: 'boolean' },
          { paramId: 'tagging', paramName: '标签管理', type: 'boolean' },
          { paramId: 'batch_ops', paramName: '批量操作', type: 'boolean' },
          { paramId: 'event_notification', paramName: '事件通知', type: 'boolean' },
          { paramId: 'cdn_integration', paramName: 'CDN集成', type: 'boolean' }
        ]
      },
      {
        groupId: 'security',
        groupName: '安全合规',
        params: [
          { paramId: 'encryption', paramName: '数据加密', type: 'text' },
          { paramId: 'access_control', paramName: '访问控制', type: 'text' },
          { paramId: 'audit_log', paramName: '审计日志', type: 'boolean' },
          { paramId: 'compliance', paramName: '合规认证', type: 'text' },
          { paramId: 'worm', paramName: 'WORM合规锁', type: 'boolean' }
        ]
      },
      {
        groupId: 'performance',
        groupName: '性能指标',
        params: [
          { paramId: 'read_throughput', paramName: '读取吞吐', unit: 'Gbps', type: 'number' },
          { paramId: 'write_throughput', paramName: '写入吞吐', unit: 'Gbps', type: 'number' },
          { paramId: 'latency', paramName: '首字节延迟', unit: 'ms', type: 'number' },
          { paramId: 'concurrent_connections', paramName: '并发连接数', type: 'number' },
          { paramId: 'qps', paramName: 'QPS上限', type: 'number' }
        ]
      },
      {
        groupId: 'service',
        groupName: '服务支持',
        params: [
          { paramId: 'sla', paramName: 'SLA可用性', type: 'text' },
          { paramId: 'support_level', paramName: '技术支持', type: 'text' },
          { paramId: 'sdk_languages', paramName: 'SDK语言', type: 'text' },
          { paramId: 'monitoring', paramName: '监控告警', type: 'boolean' },
          { paramId: 'api_access', paramName: 'API接口', type: 'boolean' }
        ]
      }
    ]
  }
};

export const PRODUCTS = [
  {
    id: 1,
    name: '轻量云服务器',
    category: 'cloud-server',
    subtitle: '入门首选',
    values: {
      region: '华北、华东',
      os_support: 'CentOS / Ubuntu',
      cpu: 2,
      memory: 4,
      instance_type: '通用型',
      deployment_mode: '单可用区',
      min_purchase: '1个月',
      billing_model: '包年包月',
      cpu_arch: 'x86_64',
      cpu_frequency: 2.5,
      cpu_benchmark: 3200,
      gpu_support: false,
      gpu_model: '—',
      burst_capability: true,
      system_disk_type: '高效云盘',
      system_disk_size: 40,
      data_disk_type: '高效云盘',
      data_disk_max: 2,
      iops: 3000,
      bandwidth_max: 1,
      ip_count: 1,
      vpc_support: true,
      ipv6: false,
      load_balancer: false,
      ddos_protection: true,
      firewall: true,
      encryption: '传输加密 (TLS)',
      compliance: '等保二级',
      sla: '99.9%',
      support_level: '工单支持 (8x5)',
      backup: '每周自动备份',
      monitoring: true,
      api_access: true
    }
  },
  {
    id: 2,
    name: '通用云服务器',
    category: 'cloud-server',
    subtitle: '企业标配',
    values: {
      region: '华北、华东、华南',
      os_support: 'CentOS / Ubuntu / Debian / Windows',
      cpu: 4,
      memory: 8,
      instance_type: '计算增强型',
      deployment_mode: '多可用区',
      min_purchase: '1个月',
      billing_model: '包年包月 / 按量付费',
      cpu_arch: 'x86_64',
      cpu_frequency: 3.0,
      cpu_benchmark: 6800,
      gpu_support: false,
      gpu_model: '—',
      burst_capability: false,
      system_disk_type: 'SSD云盘',
      system_disk_size: 80,
      data_disk_type: 'SSD云盘',
      data_disk_max: 16,
      iops: 15000,
      bandwidth_max: 5,
      ip_count: 2,
      vpc_support: true,
      ipv6: true,
      load_balancer: true,
      ddos_protection: true,
      firewall: true,
      encryption: '传输加密 + 磁盘加密',
      compliance: '等保三级',
      sla: '99.95%',
      support_level: '工单 + 电话 (24x7)',
      backup: '每日自动备份',
      monitoring: true,
      api_access: true
    }
  },
  {
    id: 3,
    name: '旗舰云服务器',
    category: 'cloud-server',
    subtitle: '性能之选',
    values: {
      region: '全部区域 (7个)',
      os_support: 'CentOS / Ubuntu / Debian / Windows / RHEL',
      cpu: 16,
      memory: 64,
      instance_type: 'GPU计算型',
      deployment_mode: '多可用区 + 异地容灾',
      min_purchase: '无限制',
      billing_model: '包年包月 / 按量 / 竞价实例',
      cpu_arch: 'x86_64 / ARM',
      cpu_frequency: 3.5,
      cpu_benchmark: 28000,
      gpu_support: true,
      gpu_model: 'NVIDIA A10G',
      burst_capability: false,
      system_disk_type: 'ESSD PL3',
      system_disk_size: 200,
      data_disk_type: 'ESSD PL3',
      data_disk_max: 64,
      iops: 100000,
      bandwidth_max: 25,
      ip_count: 5,
      vpc_support: true,
      ipv6: true,
      load_balancer: true,
      ddos_protection: true,
      firewall: true,
      encryption: '传输加密 + 磁盘加密 + KMS',
      compliance: '等保三级 / ISO27001',
      sla: '99.995%',
      support_level: '专属技术经理 (24x7)',
      backup: '实时增量备份',
      monitoring: true,
      api_access: true
    }
  },
  {
    id: 4,
    name: '标准对象存储',
    category: 'object-storage',
    subtitle: '通用存储',
    values: {
      region: '华北、华东、华南',
      storage_class: '标准 / 低频 / 归档',
      min_purchase: '无',
      billing_model: '按量付费',
      free_tier: '5GB标准存储 / 月',
      max_object_size: 5,
      max_bucket_count: 100,
      versioning: true,
      lifecycle: true,
      replication: false,
      storage_limit: '无上限',
      search: false,
      tagging: true,
      batch_ops: true,
      event_notification: true,
      cdn_integration: true,
      encryption: '服务端SSE-S3',
      access_control: 'ACL + Bucket Policy',
      audit_log: true,
      compliance: '等保二级',
      worm: false,
      read_throughput: 5,
      write_throughput: 2,
      latency: 20,
      concurrent_connections: 5000,
      qps: 3000,
      sla: '99.9%',
      support_level: '工单支持 (8x5)',
      sdk_languages: 'Java / Python / Go',
      monitoring: true,
      api_access: true
    }
  },
  {
    id: 5,
    name: '企业对象存储',
    category: 'object-storage',
    subtitle: '企业级方案',
    values: {
      region: '全部区域 (7个)',
      storage_class: '标准 / 低频 / 归档 / 深度归档',
      min_purchase: '无',
      billing_model: '按量 / 资源包',
      free_tier: '50GB标准存储 / 月',
      max_object_size: 48,
      max_bucket_count: 1000,
      versioning: true,
      lifecycle: true,
      replication: true,
      storage_limit: '无上限',
      search: true,
      tagging: true,
      batch_ops: true,
      event_notification: true,
      cdn_integration: true,
      encryption: 'SSE-S3 / SSE-KMS / CSE',
      access_control: 'ACL + Policy + STS临时授权',
      audit_log: true,
      compliance: '等保三级 / ISO27001',
      worm: true,
      read_throughput: 20,
      write_throughput: 10,
      latency: 8,
      concurrent_connections: 50000,
      qps: 30000,
      sla: '99.995%',
      support_level: '专属技术经理 (24x7)',
      sdk_languages: 'Java / Python / Go / Node / .NET / PHP',
      monitoring: true,
      api_access: true
    }
  }
];
