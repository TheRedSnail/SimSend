import axios from 'axios'

// Create axios instance
const service = axios.create({
  // Default to a relative base URL so requests are same-origin: this works
  // behind a reverse proxy (/api -> backend) and through the Vite dev proxy,
  // instead of pointing a deployed build at the visitor's localhost.
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 300000, // 5-minute timeout (ontology generation may take a long time)
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
service.interceptors.request.use(
  config => {
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor (fault-tolerant retry mechanism)
service.interceptors.response.use(
  response => {
    const res = response.data
    
    // If the returned status code is not success, throw an error
    if (!res.success && res.success !== undefined) {
      console.error('API Error:', res.error || res.message || 'Unknown error')
      return Promise.reject(new Error(res.error || res.message || 'Error'))
    }
    
    return res
  },
  error => {
    console.error('Response error:', error)
    
    // Handle timeout
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      console.error('Request timeout')
    }
    
    // Handle network error
    if (error.message === 'Network Error') {
      console.error('Network error - please check your connection')
    }
    
    return Promise.reject(error)
  }
)

// Request function with retry
export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      // Never retry a client-side timeout: the request may have reached the
      // server and still be processing, so re-sending a non-idempotent
      // create/start/generate would duplicate the work (extra projects,
      // simulations, report jobs, and LLM spend).
      if (i === maxRetries - 1 || error.code === 'ECONNABORTED') throw error

      console.warn(`Request failed, retrying (${i + 1}/${maxRetries})...`)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

export default service
