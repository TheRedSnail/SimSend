import { getCurrentScope, onScopeDispose, ref } from 'vue'

/**
 * Tracks whether the owning component/effect scope has been torn down.
 * Use it to bail out of code that runs after an `await` once the user has
 * navigated away (e.g. starting polls or calling router.replace).
 */
export function useDisposed() {
  let disposed = false
  if (getCurrentScope()) {
    onScopeDispose(() => { disposed = true })
  }
  return () => disposed
}

/**
 * Poll an async task on a setTimeout chain.
 *
 * - The next tick is scheduled only after the previous one settles, so
 *   requests never overlap.
 * - stop()/start() bump a generation counter; a tick from an older generation
 *   neither reschedules itself nor (if the task checks ctx.isStale()) applies
 *   its result.
 * - Everything stops automatically when the owning scope is disposed.
 *
 * The task receives `{ isStale }`; call it after each `await` before mutating
 * state. Returning `false` from the task stops polling.
 */
export function usePolling(task, { interval = 2000, immediate = true, onError = null } = {}) {
  const isDisposed = useDisposed()
  const isActive = ref(false)
  let generation = 0
  let timer = null

  const clearTimer = () => {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  const tick = async (gen) => {
    timer = null
    const isStale = () => gen !== generation || isDisposed()
    if (isStale()) return
    try {
      const result = await task({ isStale })
      if (result === false && !isStale()) {
        stop()
        return
      }
    } catch (error) {
      if (!isStale()) {
        if (onError) onError(error)
        else console.warn('Polling task failed:', error)
      }
    }
    if (isStale()) return
    timer = setTimeout(() => tick(gen), interval)
  }

  function start() {
    if (isDisposed()) return
    generation++
    clearTimer()
    isActive.value = true
    const gen = generation
    if (immediate) {
      tick(gen)
    } else {
      timer = setTimeout(() => tick(gen), interval)
    }
  }

  function stop() {
    generation++
    clearTimer()
    isActive.value = false
  }

  if (getCurrentScope()) {
    onScopeDispose(stop)
  }

  return { start, stop, isActive }
}
