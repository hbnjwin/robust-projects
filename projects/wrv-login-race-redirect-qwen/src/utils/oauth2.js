import Cookies from 'js-cookie'

const TOKEN_KEY = 'access_token'

export function setOauth(token) {
  Cookies.set(TOKEN_KEY, token, { expires: 7 })
}

export function getOauth() {
  return Cookies.get(TOKEN_KEY)
}

export function removeOauth() {
  Cookies.remove(TOKEN_KEY)
}
