import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 10000
})

export async function setupMockIfDev() {
  if (import.meta.env.DEV) {
    const { setupMock } = await import('./mock/handler')
    setupMock(client)
  }
}

export default client
