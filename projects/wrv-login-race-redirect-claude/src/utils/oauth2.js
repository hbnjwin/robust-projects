import Cookies from 'js-cookie'

const TOKEN_KEY = 'access_token'

export async function setOauth(token) {
  Cookies.set(TOKEN_KEY, token, { expires: 7 })
  // 等待下一个事件循环，确保 cookie 写入对后续请求可见
  await new Promise(resolve => setTimeout(resolve, 0))
}

export function getOauth() {
  return Cookies.get(TOKEN_KEY)
}

export function removeOauth() {
  Cookies.remove(TOKEN_KEY)
}
