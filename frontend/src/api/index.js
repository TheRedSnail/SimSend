import axios from 'axios'

// Create axios instance
const service = axios.create({
  // Default to a relative base URL so requests are same-origin: this works
  // behind a reverse proxy (/api -> backend) and through the Vite dev proxy,
  // instead of pointing a deployed build at the visitor's localhost.
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 300000, // 5-minute timeout (ontology generation may take a long time)
  headers: {
    'Content-Type': 'application/json',
    // The backend rejects mutating requests without this header. A custom
    // header forces a CORS preflight, so other websites can't forge requests.
    'X-SimSend-Client': '1'
  }
})

/**
 * Error raised for any failed API call. Carries the HTTP status (if any) and
 * the backend's error payload so callers can show the real message.
 */
export class ApiError extends Error {
  constructor(message, { status = null, data = null, code = null, config = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
    this.code = code
    this.config = config
  }
}

// Response interceptor
service.interceptors.response.use(
  response => {
    const res = response.data

    // Business-level failure reported with HTTP 200
    if (res && res.success === false) {
      const message = res.error || res.message || 'Request failed'
      console.error('API Error:', message)
      return Promise.reject(new ApiError(message, {
        status: response.status,
        data: res,
        config: response.config
      }))
    }

    return res
  },
  error => {
    const status = error.response?.status ?? null
    const data = error.response?.data ?? null
    let message = (data && (data.error || data.message)) || error.message || 'Request failed'

    if (error.code === 'ECONNABORTED') {
      message = 'Request timed out'
    } else if (!error.response && error.code !== 'ERR_CANCELED') {
      message = 'Network error - please check your connection'
    }

    console.error('Response error:', message)
    return Promise.reject(new ApiError(message, {
      status,
      data,
      code: error.code ?? null,
      config: error.config ?? null
    }))
  }
)

const RETRYABLE_STATUSES = new Set([502, 503, 504])

/**
 * Whether a failed request is safe and worthwhile to retry: only idempotent
 * GETs, and only on network failures or gateway errors. Timeouts are never
 * retried (the server may still be working), nor are business errors or 500s.
 */
export const isRetryable = (error) => {
  const method = (error?.config?.method || '').toLowerCase()
  if (method !== 'get') return false
  if (error.code === 'ECONNABORTED' || error.code === 'ERR_CANCELED') return false
  if (error.status == null) return true // network error, no response
  return RETRYABLE_STATUSES.has(error.status)
}

// Request function with retry (GET only; see isRetryable)
export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      if (i === maxRetries - 1 || !isRetryable(error)) throw error

      console.warn(`Request failed, retrying (${i + 1}/${maxRetries})...`)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

export default service
