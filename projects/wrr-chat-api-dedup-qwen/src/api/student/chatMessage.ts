import request from '@/config/axios'

// BUG: 与 api/ai/chatMessage.ts 完全重复的接口定义
export interface ChatMessageVO {
  id: number
  conversationId: number
  role: 'user' | 'assistant'
  content: string
  model: string
  createTime: string
}

export interface ChatConversationVO {
  id: number
  userId: number
  title: string
  model: string
  createTime: string
}

// BUG: 与 ai/ChatMessageApi 几乎完全相同
// 学生版只多了 exportChatMessage 和 submitStatus 两个方法
// 其他方法完全重复
export const ChatMessageApi = {
  getConversationList: () => {
    return request.get({ url: '/student/chat/conversation/list' })
  },
  getMessageList: (conversationId: number) => {
    return request.get({ url: '/student/chat/message/list', params: { conversationId } })
  },
  sendMessage: (data: { conversationId: number; content: string; model: string }) => {
    return request.post({ url: '/student/chat/message/send', data })
  },
  deleteConversation: (id: number) => {
    return request.delete({ url: '/student/chat/conversation/delete', params: { id } })
  },
  deleteMessage: (id: number) => {
    return request.delete({ url: '/student/chat/message/delete', params: { id } })
  },
  // 学生版独有的方法
  exportChatMessage: (conversationId: number) => {
    return request.download({ url: '/student/chat/message/export', params: { conversationId } })
  },
  submitStatus: (conversationId: number) => {
    return request.post({ url: '/student/chat/conversation/submit', data: { conversationId } })
  }
}
