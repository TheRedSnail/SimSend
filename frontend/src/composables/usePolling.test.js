import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'
import { usePolling, useDisposed } from './usePolling'

const deferred = () => {
  let resolve
  const promise = new Promise(r => { resolve = r })
  return { promise, resolve }
}

describe('usePolling', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('stops polling when its scope is disposed', async () => {
    const scope = effectScope()
    const task = vi.fn().mockResolvedValue(undefined)
    const poller = scope.run(() => usePolling(task, { interval: 1000 }))

    poller.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(task).toHaveBeenCalledTimes(1)

    scope.stop()
    await vi.advanceTimersByTimeAsync(5000)
    expect(task).toHaveBeenCalledTimes(1)
    expect(poller.isActive.value).toBe(false)
  })

  it('never overlaps requests: the next tick waits for the previous one', async () => {
    const scope = effectScope()
    const pending = deferred()
    let calls = 0
    const task = vi.fn(() => {
      calls++
      return calls === 1 ? pending.promise : Promise.resolve()
    })
    const poller = scope.run(() => usePolling(task, { interval: 1000 }))

    poller.start()
    // First request is slow; many intervals pass without a second call
    await vi.advanceTimersByTimeAsync(10000)
    expect(task).toHaveBeenCalledTimes(1)

    pending.resolve()
    await vi.advanceTimersByTimeAsync(0)
    expect(task).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1000)
    expect(task).toHaveBeenCalledTimes(2)
    scope.stop()
  })

  it('marks in-flight responses stale after stop/restart', async () => {
    const scope = effectScope()
    const pending = deferred()
    const seen = []
    let calls = 0
    const task = async ({ isStale }) => {
      calls++
      const myCall = calls
      if (myCall === 1) await pending.promise
      seen.push({ call: myCall, stale: isStale() })
    }
    const poller = scope.run(() => usePolling(task, { interval: 1000 }))

    poller.start()
    await vi.advanceTimersByTimeAsync(0)
    poller.stop()
    poller.start() // new generation; call 2 runs immediately
    await vi.advanceTimersByTimeAsync(0)
    pending.resolve()
    await vi.advanceTimersByTimeAsync(0)

    expect(seen).toContainEqual({ call: 1, stale: true })
    expect(seen).toContainEqual({ call: 2, stale: false })
    scope.stop()
  })

  it('stops when the task returns false', async () => {
    const scope = effectScope()
    const task = vi.fn().mockResolvedValue(false)
    const poller = scope.run(() => usePolling(task, { interval: 1000 }))

    poller.start()
    await vi.advanceTimersByTimeAsync(5000)
    expect(task).toHaveBeenCalledTimes(1)
    expect(poller.isActive.value).toBe(false)
    scope.stop()
  })

  it('keeps polling after a task error and reports it', async () => {
    const scope = effectScope()
    const onError = vi.fn()
    const task = vi.fn().mockRejectedValueOnce(new Error('boom')).mockResolvedValue(undefined)
    const poller = scope.run(() => usePolling(task, { interval: 1000, onError }))

    poller.start()
    await vi.advanceTimersByTimeAsync(1000)
    expect(onError).toHaveBeenCalledTimes(1)
    expect(task).toHaveBeenCalledTimes(2)
    scope.stop()
  })

  it('cannot be started after disposal', async () => {
    const scope = effectScope()
    const task = vi.fn().mockResolvedValue(undefined)
    const poller = scope.run(() => usePolling(task, { interval: 1000 }))
    scope.stop()
    poller.start()
    await vi.advanceTimersByTimeAsync(5000)
    expect(task).not.toHaveBeenCalled()
  })
})

describe('useDisposed', () => {
  it('flips to true when the scope is disposed', () => {
    const scope = effectScope()
    const isDisposed = scope.run(() => useDisposed())
    expect(isDisposed()).toBe(false)
    scope.stop()
    expect(isDisposed()).toBe(true)
  })
})
