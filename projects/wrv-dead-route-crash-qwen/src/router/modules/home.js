import Layout from '@/layout/index.vue'

export default [
  {
    path: '/',
    component: Layout,
    redirect: '/home/create-review',
    children: [
      { path: 'create-review', component: () => import('@/pages/home/create-review.vue') },
      { path: 'allocation-review', component: () => import('@/pages/home/allocation-review.vue') },
      { path: 'data-upload', component: () => import('@/pages/home/data-upload.vue') },
      { path: 'document-prereview', component: () => import('@/pages/home/document-prereview.vue') },
      { path: 'report-prereview', component: () => import('@/pages/home/report-prereview.vue') },
      { path: 'report-substantive-examination', component: () => import('@/pages/home/report-substantive-examination.vue') },
      { path: 'opinion-generation', component: () => import('@/pages/home/opinion-generation.vue') },
      { path: 'archive', component: () => import('@/pages/home/archive.vue') },
    ]
  }
]
