const BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const MODE = import.meta.env.VITE_API_MODE || 'real'

export class ApiError extends Error {
  constructor(message, status = 500, details = {}) { super(message); this.status = status; this.details = details }
}

export async function api(path, options = {}) {
  if (MODE === 'mock') throw new ApiError('当前展示原型尚未启用 Mock 适配，请切换到真实接口。', 503)
  let response
  try {
    response = await fetch(`${BASE}${path}`, {
      ...options,
      headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
    })
  } catch {
    throw new ApiError('连接本机服务失败。请确认已启动配置中的后端服务。', 503)
  }
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new ApiError(body.message || '请求未完成', response.status, body.details || {})
  return body.data
}

export const get = (path) => api(path)
export const post = (path, value) => api(path, { method: 'POST', body: JSON.stringify(value) })
export const put = (path, value) => api(path, { method: 'PUT', body: JSON.stringify(value) })

