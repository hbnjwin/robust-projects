export default {
  system: {
    login: {
      title: '用户登录',
      username: '用户名',
      password: '密码',
      rememberMe: '记住我',
      forgotPassword: '忘记密码？',
      submit: '登录',
      register: '注册账号',
      loginSuccess: '登录成功',
      loginFailed: '用户名或密码错误',
      logout: '退出登录',
      logoutConfirm: '确定要退出登录吗？',
      expired: '登录已过期，请重新登录'
    },
    register: {
      title: '注册',
      username: '用户名',
      password: '密码',
      confirmPassword: '确认密码',
      email: '邮箱',
      phone: '手机号',
      code: '验证码',
      getCode: '获取验证码',
      submit: '注册',
      success: '注册成功',
      hasAccount: '已有账号？去登录'
    },
    menu: {
      home: '首页',
      dashboard: '工作台',
      course: '课程管理',
      student: '学员管理',
      homework: '作业管理',
      exam: '考试管理',
      teacher: '教师管理',
      order: '订单管理',
      content: '内容管理',
      system: '系统管理',
      user: '用户管理',
      role: '角色管理',
      permission: '权限管理',
      dict: '字典管理',
      config: '系统配置',
      log: '操作日志',
      statistics: '数据统计',
      notification: '消息通知',
      profile: '个人中心',
      settings: '系统设置'
    },
    header: {
      profile: '个人中心',
      settings: '系统设置',
      logout: '退出登录',
      fullscreen: '全屏',
      exitFullscreen: '退出全屏',
      notification: '消息通知',
      language: '语言切换',
      theme: '主题设置'
    },
    footer: {
      copyright: '版权所有',
      technicalSupport: '技术支持'
    },
    error: {
      notFound: '页面不存在',
      forbidden: '无权限访问',
      serverError: '服务器错误',
      networkError: '网络连接失败',
      backHome: '返回首页',
      retry: '重试'
    }
  },
  common: {
    action: {
      add: '新增',
      edit: '编辑',
      delete: '删除',
      save: '保存',
      cancel: '取消',
      confirm: '确定',
      search: '搜索',
      reset: '重置',
      export: '导出',
      import: '导入',
      upload: '上传',
      download: '下载',
      preview: '预览',
      refresh: '刷新',
      back: '返回',
      submit: '提交',
      close: '关闭',
      more: '更多',
      detail: '详情',
      view: '查看',
      copy: '复制',
      enable: '启用',
      disable: '禁用',
      batchDelete: '批量删除',
      expand: '展开',
      collapse: '收起',
      selectAll: '全选',
      print: '打印'
    },
    status: {
      enable: '启用',
      disable: '禁用',
      success: '成功',
      failed: '失败',
      pending: '待处理',
      processing: '处理中',
      completed: '已完成',
      cancelled: '已取消',
      draft: '草稿',
      published: '已发布',
      archived: '已归档',
      yes: '是',
      no: '否'
    },
    message: {
      addSuccess: '新增成功',
      editSuccess: '编辑成功',
      deleteSuccess: '删除成功',
      saveSuccess: '保存成功',
      submitSuccess: '提交成功',
      operateSuccess: '操作成功',
      operateFailed: '操作失败',
      deleteConfirm: '确定要删除吗？此操作不可撤销。',
      batchDeleteConfirm: '确定要批量删除选中的 {count} 条记录吗？',
      selectRequired: '请至少选择一条记录',
      uploadSuccess: '上传成功',
      uploadFailed: '上传失败',
      exportSuccess: '导出成功',
      importSuccess: '导入成功',
      copySuccess: '复制成功',
      loading: '加载中...',
      noData: '暂无数据',
      networkError: '网络请求失败，请稍后重试',
      timeout: '请求超时，请稍后重试'
    },
    placeholder: {
      input: '请输入',
      select: '请选择',
      search: '请输入关键词搜索',
      startDate: '开始日期',
      endDate: '结束日期',
      startTime: '开始时间',
      endTime: '结束时间'
    },
    table: {
      index: '序号',
      action: '操作',
      createTime: '创建时间',
      updateTime: '更新时间',
      creator: '创建人',
      status: '状态',
      remark: '备注',
      total: '共 {total} 条',
      selected: '已选择 {count} 项'
    },
    validate: {
      required: '此字段为必填项',
      email: '请输入正确的邮箱格式',
      phone: '请输入正确的手机号格式',
      number: '请输入数字',
      maxLength: '长度不能超过 {max} 个字符',
      minLength: '长度不能少于 {min} 个字符',
      passwordStrength: '密码需要包含大小写字母和数字',
      passwordMatch: '两次输入的密码不一致'
    }
  },
  course: {
    title: '课程管理',
    name: '课程名称',
    category: '课程分类',
    teacher: '授课教师',
    cover: '课程封面',
    price: '课程价格',
    free: '免费',
    duration: '课时时长',
    studentCount: '学员人数',
    status: '课程状态',
    description: '课程简介',
    content: '课程内容',
    chapter: '章节',
    section: '课时',
    addChapter: '添加章节',
    addSection: '添加课时',
    publish: '发布课程',
    offline: '下架课程',
    statusOptions: {
      draft: '草稿',
      published: '已上架',
      offline: '已下架'
    },
    detail: {
      basicInfo: '基本信息',
      chapterList: '章节列表',
      studentList: '学员列表',
      comments: '课程评价',
      statistics: '学习统计'
    }
  },
  student: {
    title: '学员管理',
    name: '学员姓名',
    avatar: '头像',
    gender: '性别',
    phone: '手机号',
    email: '邮箱',
    enrollTime: '注册时间',
    lastLogin: '最近登录',
    courseCount: '报名课程数',
    status: '状态',
    genderOptions: {
      male: '男',
      female: '女',
      unknown: '未知'
    },
    detail: {
      basicInfo: '基本信息',
      courseList: '课程列表',
      homeworkList: '作业列表',
      studyRecord: '学习记录',
      examRecord: '考试记录'
    },
    study: {
      progress: '学习进度',
      duration: '学习时长',
      lastStudy: '上次学习',
      completed: '已完成',
      incomplete: '未完成'
    }
  },
  homework: {
    title: '作业管理',
    name: '作业名称',
    course: '所属课程',
    type: '作业类型',
    deadline: '截止时间',
    submitCount: '提交人数',
    totalCount: '应交人数',
    gradeStatus: '批改状态',
    score: '分数',
    content: '作业内容',
    answer: '参考答案',
    attachment: '附件',
    feedback: '批改反馈',
    submit: '提交作业',
    grade: '批改',
    typeOptions: {
      essay: '论述题',
      choice: '选择题',
      practice: '实操题',
      upload: '文件上传'
    },
    statusOptions: {
      unsubmitted: '未提交',
      submitted: '已提交',
      graded: '已批改',
      returned: '已退回'
    }
  },
  exam: {
    title: '考试管理',
    name: '考试名称',
    course: '关联课程',
    startTime: '开始时间',
    endTime: '结束时间',
    duration: '考试时长',
    totalScore: '总分',
    passScore: '及格分',
    questionCount: '题目数量',
    participantCount: '参加人数',
    status: '考试状态',
    statusOptions: {
      notStarted: '未开始',
      inProgress: '进行中',
      ended: '已结束'
    },
    result: {
      score: '得分',
      rank: '排名',
      pass: '通过',
      fail: '未通过',
      averageScore: '平均分',
      highestScore: '最高分',
      lowestScore: '最低分'
    }
  },
  teacher: {
    title: '教师管理',
    name: '教师姓名',
    avatar: '头像',
    phone: '手机号',
    email: '邮箱',
    subject: '授课科目',
    courseCount: '课程数',
    studentCount: '学员数',
    rating: '评分',
    introduction: '教师简介',
    status: '状态'
  },
  order: {
    title: '订单管理',
    orderNo: '订单号',
    course: '购买课程',
    student: '学员',
    amount: '订单金额',
    payAmount: '实付金额',
    payMethod: '支付方式',
    payTime: '支付时间',
    createTime: '创建时间',
    status: '订单状态',
    remark: '备注',
    refund: '退款',
    statusOptions: {
      unpaid: '待支付',
      paid: '已支付',
      refunding: '退款中',
      refunded: '已退款',
      closed: '已关闭'
    },
    payMethodOptions: {
      wechat: '微信支付',
      alipay: '支付宝',
      bank: '银行转账'
    }
  },
  content: {
    title: '内容管理',
    article: {
      title: '文章管理',
      name: '文章标题',
      category: '文章分类',
      author: '作者',
      cover: '封面',
      summary: '摘要',
      content: '正文',
      publishTime: '发布时间',
      viewCount: '浏览量',
      status: '状态'
    },
    notice: {
      title: '公告管理',
      name: '公告标题',
      content: '公告内容',
      type: '公告类型',
      publishTime: '发布时间',
      typeOptions: {
        system: '系统公告',
        activity: '活动通知',
        update: '更新通知'
      }
    },
    banner: {
      title: '轮播管理',
      image: '轮播图片',
      link: '跳转链接',
      sort: '排序',
      status: '状态'
    }
  },
  statistics: {
    title: '数据统计',
    overview: '数据概览',
    totalStudents: '总学员数',
    totalCourses: '总课程数',
    totalOrders: '总订单数',
    totalRevenue: '总收入',
    todayNew: '今日新增',
    weekNew: '本周新增',
    monthNew: '本月新增',
    trend: '趋势分析',
    distribution: '分布统计',
    ranking: '排行榜',
    chart: {
      studentTrend: '学员增长趋势',
      orderTrend: '订单趋势',
      revenueTrend: '收入趋势',
      courseDistribution: '课程分布',
      payMethodDistribution: '支付方式分布'
    }
  },
  notification: {
    title: '消息通知',
    all: '全部',
    unread: '未读',
    read: '已读',
    markRead: '标记已读',
    markAllRead: '全部标记已读',
    delete: '删除',
    empty: '暂无消息',
    type: {
      system: '系统消息',
      course: '课程通知',
      homework: '作业通知',
      order: '订单通知'
    }
  },
  profile: {
    title: '个人中心',
    basicInfo: '基本信息',
    avatar: '头像',
    nickname: '昵称',
    username: '用户名',
    phone: '手机号',
    email: '邮箱',
    changePassword: '修改密码',
    oldPassword: '当前密码',
    newPassword: '新密码',
    confirmPassword: '确认密码',
    updateSuccess: '更新成功'
  },
  dashboard: {
    title: '工作台',
    welcome: '欢迎回来',
    quickAction: '快捷操作',
    recentCourse: '最近课程',
    todoList: '待办事项',
    announcement: '最新公告',
    myStatistics: '我的统计'
  }
}
