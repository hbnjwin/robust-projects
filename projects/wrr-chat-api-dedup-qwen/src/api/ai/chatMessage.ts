import request from '@/config/axios'

// AI 对话消息 API
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

// BUG (refactor needed): 这个文件和 student/chatMessage.ts 几乎完全一样
// ChatMessageVO 接口定义了两份
// ChatMessageApi 对象也重复了
// 应该提取公共部分到 shared 模块

export const ChatMessageApi = {
  getConversationList: () => {
    return request.get({ url: '/ai/chat/conversation/list' })
  },
  getMessageList: (conversationId: number) => {
    return request.get({ url: '/ai/chat/message/list', params: { conversationId } })
  },
  sendMessage: (data: { conversationId: number; content: string; model: string }) => {
    return request.post({ url: '/ai/chat/message/send', data })
  },
  deleteConversation: (id: number) => {
    return request.delete({ url: '/ai/chat/conversation/delete', params: { id } })
  },
  deleteMessage: (id: number) => {
    return request.delete({ url: '/ai/chat/message/delete', params: { id } })
  }
}
