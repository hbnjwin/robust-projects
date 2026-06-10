export default {
  system: {
    login: {
      title: 'User Login',
      username: 'Username',
      password: 'Password',
      rememberMe: 'Remember Me',
      forgotPassword: 'Forgot Password?',
      submit: 'Login',
      register: 'Register',
      loginSuccess: 'Login Successful',
      loginFailed: 'Invalid username or password',
      logout: 'Logout',
      logoutConfirm: 'Are you sure you want to logout?',
      expired: 'Session expired, please login again'
    },
    register: {
      title: 'Register',
      username: 'Username',
      password: 'Password',
      confirmPassword: 'Confirm Password',
      email: 'Email',
      phone: 'Phone',
      code: 'Verification Code',
      getCode: 'Get Code',
      submit: 'Register',
      success: 'Registration Successful',
      hasAccount: 'Already have an account? Login'
    },
    menu: {
      home: 'Home',
      dashboard: 'Dashboard',
      course: 'Courses',
      student: 'Students',
      homework: 'Homework',
      exam: 'Exams',
      teacher: 'Teachers',
      order: 'Orders',
      content: 'Content',
      system: 'System',
      user: 'Users',
      role: 'Roles',
      permission: 'Permissions',
      dict: 'Dictionary',
      config: 'Configuration',
      log: 'Operation Logs',
      statistics: 'Statistics',
      notification: 'Notifications',
      profile: 'Profile',
      settings: 'Settings'
    },
    header: {
      profile: 'Profile',
      settings: 'Settings',
      logout: 'Logout',
      fullscreen: 'Fullscreen',
      exitFullscreen: 'Exit Fullscreen',
      notification: 'Notifications',
      language: 'Language',
      theme: 'Theme'
    },
    footer: {
      copyright: 'Copyright',
      technicalSupport: 'Technical Support'
    },
    error: {
      notFound: 'Page Not Found',
      forbidden: 'Access Denied',
      serverError: 'Server Error',
      networkError: 'Network Error',
      backHome: 'Back to Home',
      retry: 'Retry'
    }
  },
  common: {
    action: {
      add: 'Add',
      edit: 'Edit',
      delete: 'Delete',
      save: 'Save',
      cancel: 'Cancel',
      confirm: 'Confirm',
      search: 'Search',
      reset: 'Reset',
      export: 'Export',
      import: 'Import',
      upload: 'Upload',
      download: 'Download',
      preview: 'Preview',
      refresh: 'Refresh',
      back: 'Back',
      submit: 'Submit',
      close: 'Close',
      more: 'More',
      detail: 'Detail',
      view: 'View',
      copy: 'Copy',
      enable: 'Enable',
      disable: 'Disable',
      batchDelete: 'Batch Delete',
      expand: 'Expand',
      collapse: 'Collapse',
      selectAll: 'Select All',
      print: 'Print'
    },
    status: {
      enable: 'Enabled',
      disable: 'Disabled',
      success: 'Success',
      failed: 'Failed',
      pending: 'Pending',
      processing: 'Processing',
      completed: 'Completed',
      cancelled: 'Cancelled',
      draft: 'Draft',
      published: 'Published',
      archived: 'Archived',
      yes: 'Yes',
      no: 'No'
    },
    message: {
      addSuccess: 'Added successfully',
      editSuccess: 'Updated successfully',
      deleteSuccess: 'Deleted successfully',
      saveSuccess: 'Saved successfully',
      submitSuccess: 'Submitted successfully',
      operateSuccess: 'Operation successful',
      operateFailed: 'Operation failed',
      deleteConfirm: 'Are you sure you want to delete? This action cannot be undone.',
      batchDeleteConfirm: 'Are you sure you want to delete the selected {count} records?',
      selectRequired: 'Please select at least one record',
      uploadSuccess: 'Uploaded successfully',
      uploadFailed: 'Upload failed',
      exportSuccess: 'Exported successfully',
      importSuccess: 'Imported successfully',
      copySuccess: 'Copied successfully',
      loading: 'Loading...',
      noData: 'No data',
      networkError: 'Network request failed, please try again later',
      timeout: 'Request timed out, please try again later'
    },
    placeholder: {
      input: 'Please enter',
      select: 'Please select',
      search: 'Search by keyword',
      startDate: 'Start Date',
      endDate: 'End Date',
      startTime: 'Start Time',
      endTime: 'End Time'
    },
    table: {
      index: 'No.',
      action: 'Actions',
      createTime: 'Created At',
      updateTime: 'Updated At',
      creator: 'Created By',
      status: 'Status',
      remark: 'Remark',
      total: '{total} records',
      selected: '{count} selected'
    },
    validate: {
      required: 'This field is required',
      email: 'Please enter a valid email address',
      phone: 'Please enter a valid phone number',
      number: 'Please enter a number',
      maxLength: 'Must not exceed {max} characters',
      minLength: 'Must be at least {min} characters',
      passwordStrength: 'Password must contain uppercase, lowercase letters and numbers',
      passwordMatch: 'Passwords do not match'
    }
  },
  course: {
    title: 'Course Management',
    name: 'Course Name',
    category: 'Category',
    teacher: 'Instructor',
    cover: 'Cover Image',
    price: 'Price',
    free: 'Free',
    duration: 'Duration',
    studentCount: 'Students',
    status: 'Status',
    description: 'Description',
    content: 'Content',
    chapter: 'Chapter',
    section: 'Section',
    addChapter: 'Add Chapter',
    addSection: 'Add Section',
    publish: 'Publish',
    offline: 'Unpublish',
    statusOptions: {
      draft: 'Draft',
      published: 'Published',
      offline: 'Unpublished'
    },
    detail: {
      basicInfo: 'Basic Info',
      chapterList: 'Chapters',
      studentList: 'Students',
      comments: 'Reviews',
      statistics: 'Study Statistics'
    }
  },
  student: {
    title: 'Student Management',
    name: 'Name',
    avatar: 'Avatar',
    gender: 'Gender',
    phone: 'Phone',
    email: 'Email',
    enrollTime: 'Registration Date',
    lastLogin: 'Last Login',
    courseCount: 'Enrolled Courses',
    status: 'Status',
    genderOptions: {
      male: 'Male',
      female: 'Female',
      unknown: 'Unknown'
    },
    detail: {
      basicInfo: 'Basic Info',
      courseList: 'Courses',
      homeworkList: 'Homework',
      studyRecord: 'Study Record',
      examRecord: 'Exam Record'
    },
    study: {
      progress: 'Progress',
      duration: 'Study Duration',
      lastStudy: 'Last Study',
      completed: 'Completed',
      incomplete: 'Incomplete'
    }
  },
  homework: {
    title: 'Homework Management',
    name: 'Homework Name',
    course: 'Course',
    type: 'Type',
    deadline: 'Deadline',
    submitCount: 'Submissions',
    totalCount: 'Total Students',
    gradeStatus: 'Grading Status',
    score: 'Score',
    content: 'Content',
    answer: 'Reference Answer',
    attachment: 'Attachment',
    feedback: 'Feedback',
    submit: 'Submit',
    grade: 'Grade',
    typeOptions: {
      essay: 'Essay',
      choice: 'Multiple Choice',
      practice: 'Practice',
      upload: 'File Upload'
    },
    statusOptions: {
      unsubmitted: 'Not Submitted',
      submitted: 'Submitted',
      graded: 'Graded',
      returned: 'Returned'
    }
  },
  exam: {
    title: 'Exam Management',
    name: 'Exam Name',
    course: 'Course',
    startTime: 'Start Time',
    endTime: 'End Time',
    duration: 'Duration',
    totalScore: 'Total Score',
    passScore: 'Pass Score',
    questionCount: 'Questions',
    participantCount: 'Participants',
    status: 'Status',
    statusOptions: {
      notStarted: 'Not Started',
      inProgress: 'In Progress',
      ended: 'Ended'
    },
    result: {
      score: 'Score',
      rank: 'Rank',
      pass: 'Pass',
      fail: 'Fail',
      averageScore: 'Average Score',
      highestScore: 'Highest Score',
      lowestScore: 'Lowest Score'
    }
  },
  teacher: {
    title: 'Teacher Management',
    name: 'Name',
    avatar: 'Avatar',
    phone: 'Phone',
    email: 'Email',
    subject: 'Subject',
    courseCount: 'Courses',
    studentCount: 'Students',
    rating: 'Rating',
    introduction: 'Introduction',
    status: 'Status'
  },
  order: {
    title: 'Order Management',
    orderNo: 'Order No.',
    course: 'Course',
    student: 'Student',
    amount: 'Amount',
    payAmount: 'Paid Amount',
    payMethod: 'Payment Method',
    payTime: 'Payment Time',
    createTime: 'Created At',
    status: 'Status',
    remark: 'Remark',
    refund: 'Refund',
    statusOptions: {
      unpaid: 'Unpaid',
      paid: 'Paid',
      refunding: 'Refunding',
      refunded: 'Refunded',
      closed: 'Closed'
    },
    payMethodOptions: {
      wechat: 'WeChat Pay',
      alipay: 'Alipay',
      bank: 'Bank Transfer'
    }
  },
  content: {
    title: 'Content Management',
    article: {
      title: 'Articles',
      name: 'Title',
      category: 'Category',
      author: 'Author',
      cover: 'Cover',
      summary: 'Summary',
      content: 'Content',
      publishTime: 'Published At',
      viewCount: 'Views',
      status: 'Status'
    },
    notice: {
      title: 'Announcements',
      name: 'Title',
      content: 'Content',
      type: 'Type',
      publishTime: 'Published At',
      typeOptions: {
        system: 'System',
        activity: 'Activity',
        update: 'Update'
      }
    },
    banner: {
      title: 'Banners',
      image: 'Image',
      link: 'Link',
      sort: 'Sort Order',
      status: 'Status'
    }
  },
  statistics: {
    title: 'Statistics',
    overview: 'Overview',
    totalStudents: 'Total Students',
    totalCourses: 'Total Courses',
    totalOrders: 'Total Orders',
    totalRevenue: 'Total Revenue',
    todayNew: 'Today',
    weekNew: 'This Week',
    monthNew: 'This Month',
    trend: 'Trend Analysis',
    distribution: 'Distribution',
    ranking: 'Ranking',
    chart: {
      studentTrend: 'Student Growth',
      orderTrend: 'Order Trend',
      revenueTrend: 'Revenue Trend',
      courseDistribution: 'Course Distribution',
      payMethodDistribution: 'Payment Distribution'
    }
  },
  notification: {
    title: 'Notifications',
    all: 'All',
    unread: 'Unread',
    read: 'Read',
    markRead: 'Mark as Read',
    markAllRead: 'Mark All as Read',
    delete: 'Delete',
    empty: 'No notifications',
    type: {
      system: 'System',
      course: 'Course',
      homework: 'Homework',
      order: 'Order'
    }
  },
  profile: {
    title: 'Profile',
    basicInfo: 'Basic Info',
    avatar: 'Avatar',
    nickname: 'Nickname',
    username: 'Username',
    phone: 'Phone',
    email: 'Email',
    changePassword: 'Change Password',
    oldPassword: 'Current Password',
    newPassword: 'New Password',
    confirmPassword: 'Confirm Password',
    updateSuccess: 'Updated successfully'
  },
  dashboard: {
    title: 'Dashboard',
    welcome: 'Welcome Back',
    quickAction: 'Quick Actions',
    recentCourse: 'Recent Courses',
    todoList: 'To-Do List',
    announcement: 'Announcements',
    myStatistics: 'My Statistics'
  }
}
