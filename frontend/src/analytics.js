// Umami analytics for the landing page.
//
// The backend serves the Umami settings at /api/site-config (from
// UMAMI_SCRIPT_URL / UMAMI_WEBSITE_ID in .env); when they aren't set, nothing
// is loaded and every call here is a no-op. The script is loaded with
// auto-tracking off, so only what the landing page reports is tracked and the
// app's own screens never are. Never pass names, emails or other personal
// data as event data.

import service from './api/index'

const fetchSiteConfig = async () => {
  const res = await service.get('/api/site-config', { timeout: 5000 })
  return res?.data?.umami ?? null
}

export function createAnalytics({ win, doc, fetchConfig = fetchSiteConfig } = {}) {
  let loading = null
  // Calls are chained so they reach Umami in order, after the script loads.
  let queue = Promise.resolve()

  const injectScript = ({ scriptUrl, websiteId }) => new Promise((resolve) => {
    const el = doc.createElement('script')
    el.src = scriptUrl
    el.defer = true
    el.dataset.websiteId = websiteId
    el.dataset.autoTrack = 'false'
    el.onload = () => resolve(Boolean(win.umami?.track))
    el.onerror = () => resolve(false) // blocked by an ad blocker, offline, ...
    doc.head.appendChild(el)
  })

  const load = () => {
    if (!loading) {
      loading = Promise.resolve()
        .then(fetchConfig)
        .then((umami) => (umami ? injectScript(umami) : false))
        .catch(() => false)
    }
    return loading
  }

  const send = (args) => {
    if (!loading) return
    queue = queue
      .then(() => loading)
      .then((ok) => {
        if (ok) win.umami.track(...args)
      })
      .catch(() => {})
  }

  return {
    load,
    /** Record a page view of the current URL and title. */
    pageview: () => send([]),
    /** Record a named event with optional (non-personal) data. */
    track: (event, data) => send(data === undefined ? [event] : [event, data]),
    /** Resolves once every call so far has been handed to Umami (for tests). */
    flushed: () => queue
  }
}

const analytics = typeof window === 'undefined'
  ? createAnalytics({ win: {}, doc: null, fetchConfig: async () => null })
  : createAnalytics({ win: window, doc: document })

export default analytics
