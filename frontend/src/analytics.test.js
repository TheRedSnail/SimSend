import { describe, expect, it, vi } from 'vitest'
import { createAnalytics } from './analytics'

const UMAMI = { scriptUrl: 'https://analytics.example.com/script.js', websiteId: 'abc-123' }

// Minimal stand-ins for window/document: appending the script "loads" it by
// installing a fake umami global and firing onload.
function fakeBrowser({ loads = true } = {}) {
  const win = {}
  const umamiTrack = vi.fn()
  const appended = []
  const doc = {
    createElement: () => ({ dataset: {} }),
    head: {
      appendChild: (el) => {
        appended.push(el)
        queueMicrotask(() => {
          if (loads) {
            win.umami = { track: umamiTrack }
            el.onload?.()
          } else {
            el.onerror?.()
          }
        })
      }
    }
  }
  return { win, doc, umamiTrack, appended }
}

const configFetcher = (umami) => vi.fn(async () => umami)

describe('analytics', () => {
  it('loads the Umami script with auto-tracking off', async () => {
    const b = fakeBrowser()
    const a = createAnalytics({ win: b.win, doc: b.doc, fetchConfig: configFetcher(UMAMI) })
    expect(await a.load()).toBe(true)

    expect(b.appended).toHaveLength(1)
    const [el] = b.appended
    expect(el.src).toBe(UMAMI.scriptUrl)
    expect(el.defer).toBe(true)
    expect(el.dataset.websiteId).toBe(UMAMI.websiteId)
    expect(el.dataset.autoTrack).toBe('false')
  })

  it('loads only once', async () => {
    const b = fakeBrowser()
    const fetchConfig = configFetcher(UMAMI)
    const a = createAnalytics({ win: b.win, doc: b.doc, fetchConfig })
    await Promise.all([a.load(), a.load()])
    await a.load()
    expect(fetchConfig).toHaveBeenCalledTimes(1)
    expect(b.appended).toHaveLength(1)
  })

  it('sends page views and events once loaded, including calls made before', async () => {
    const b = fakeBrowser()
    const a = createAnalytics({ win: b.win, doc: b.doc, fetchConfig: configFetcher(UMAMI) })
    const loading = a.load()
    a.pageview()
    a.track('cta-click', { button: 'hero' })
    await loading
    await a.flushed()

    expect(b.umamiTrack).toHaveBeenNthCalledWith(1)
    expect(b.umamiTrack).toHaveBeenNthCalledWith(2, 'cta-click', { button: 'hero' })
  })

  it('does nothing when Umami is not configured', async () => {
    const b = fakeBrowser()
    const a = createAnalytics({ win: b.win, doc: b.doc, fetchConfig: configFetcher(null) })
    expect(await a.load()).toBe(false)
    a.track('signup')
    await a.flushed()
    expect(b.appended).toHaveLength(0)
    expect(b.umamiTrack).not.toHaveBeenCalled()
  })

  it('does nothing when load() was never called', async () => {
    const b = fakeBrowser()
    const a = createAnalytics({ win: b.win, doc: b.doc, fetchConfig: configFetcher(UMAMI) })
    a.track('signup')
    await a.flushed()
    expect(b.appended).toHaveLength(0)
  })

  it('survives a failing config request or a blocked script', async () => {
    const failing = fakeBrowser()
    const a = createAnalytics({
      win: failing.win,
      doc: failing.doc,
      fetchConfig: vi.fn(async () => { throw new Error('offline') })
    })
    expect(await a.load()).toBe(false)

    const blocked = fakeBrowser({ loads: false })
    const b = createAnalytics({ win: blocked.win, doc: blocked.doc, fetchConfig: configFetcher(UMAMI) })
    expect(await b.load()).toBe(false)
    expect(() => b.track('signup')).not.toThrow()
    await b.flushed()
  })

  it('swallows errors thrown by umami.track', async () => {
    const b = fakeBrowser()
    const a = createAnalytics({ win: b.win, doc: b.doc, fetchConfig: configFetcher(UMAMI) })
    await a.load()
    b.umamiTrack.mockImplementation(() => { throw new Error('boom') })
    expect(() => a.track('signup')).not.toThrow()
    await a.flushed()
  })
})
