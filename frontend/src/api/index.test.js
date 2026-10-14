import { afterEach, describe, expect, it, vi } from 'vitest'
import service, { ApiError, isRetryable, requestWithRetry } from './index'

// Route requests through a fake adapter instead of the network
const withAdapter = (adapter) => {
  const original = service.defaults.adapter
  service.defaults.adapter = adapter
  return () => { service.defaults.adapter = original }
}

const reply = (config, status, data) => {
  const response = { data, status, statusText: String(status), headers: {}, config }
  if (status >= 200 && status < 300) return Promise.resolve(response)
  const err = new Error(`Request failed with status code ${status}`)
  err.config = config
  err.response = response
  err.isAxiosError = true
  return Promise.reject(err)
}

describe('api client', () => {
  let restore = () => {}
  afterEach(() => restore())

  it('sends the X-SimSend-Client header', async () => {
    let seenHeaders = null
    restore = withAdapter(config => {
      seenHeaders = config.headers
      return reply(config, 200, { success: true })
    })
    await service.post('/api/x', {})
    expect(seenHeaders['X-SimSend-Client']).toBe('1')
  })

  it("surfaces the backend's error message and status", async () => {
    restore = withAdapter(config => reply(config, 409, { success: false, error: 'Too many simulations running' }))
    const err = await service.post('/api/simulation/start', {}).catch(e => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toBe('Too many simulations running')
    expect(err.status).toBe(409)
  })

  it('rejects business errors reported with HTTP 200', async () => {
    restore = withAdapter(config => reply(config, 200, { success: false, error: 'nope' }))
    const err = await service.get('/api/x').catch(e => e)
    expect(err.message).toBe('nope')
  })
})

describe('requestWithRetry', () => {
  let restore = () => {}
  afterEach(() => {
    restore()
    vi.useRealTimers()
  })

  it('never retries a POST', async () => {
    const adapter = vi.fn(config => reply(config, 503, { success: false, error: 'busy' }))
    restore = withAdapter(adapter)
    await expect(requestWithRetry(() => service.post('/api/x', {}), 3, 1)).rejects.toThrow('busy')
    expect(adapter).toHaveBeenCalledTimes(1)
  })

  it('does not retry a GET that failed with 500', async () => {
    const adapter = vi.fn(config => reply(config, 500, { success: false, error: 'boom' }))
    restore = withAdapter(adapter)
    await expect(requestWithRetry(() => service.get('/api/x'), 3, 1)).rejects.toThrow('boom')
    expect(adapter).toHaveBeenCalledTimes(1)
  })

  it('does not retry business errors', async () => {
    const adapter = vi.fn(config => reply(config, 200, { success: false, error: 'bad' }))
    restore = withAdapter(adapter)
    await expect(requestWithRetry(() => service.get('/api/x'), 3, 1)).rejects.toThrow('bad')
    expect(adapter).toHaveBeenCalledTimes(1)
  })

  it('retries a GET on 503 and then succeeds', async () => {
    let calls = 0
    const adapter = vi.fn(config => {
      calls++
      return calls < 3 ? reply(config, 503, {}) : reply(config, 200, { success: true, data: 1 })
    })
    restore = withAdapter(adapter)
    const res = await requestWithRetry(() => service.get('/api/x'), 3, 1)
    expect(res.data).toBe(1)
    expect(adapter).toHaveBeenCalledTimes(3)
  })
})

describe('isRetryable', () => {
  const get = { method: 'get' }
  it('only allows network errors and gateway errors on GET', () => {
    expect(isRetryable(new ApiError('x', { config: get }))).toBe(true)
    expect(isRetryable(new ApiError('x', { config: get, status: 502 }))).toBe(true)
    expect(isRetryable(new ApiError('x', { config: get, status: 500 }))).toBe(false)
    expect(isRetryable(new ApiError('x', { config: get, code: 'ECONNABORTED' }))).toBe(false)
    expect(isRetryable(new ApiError('x', { config: { method: 'post' } }))).toBe(false)
  })
})
