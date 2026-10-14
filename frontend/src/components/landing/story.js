// Content and scroll math for the landing page's scroll story (/welcome).
//
// The sample run is illustrative: it follows the Velora test brief. Swap in a
// recorded run's posts and numbers before treating any of it as real output.

export const CHAPTER_COUNT = 5

// Share of each chapter's scroll spent building its visual; the rest holds
// the finished state so it can be read before the next chapter starts.
const BUILD_SHARE = 0.7

const clamp01 = (x) => Math.max(0, Math.min(1, x))

/**
 * Map overall story progress (0..1) to the active chapter and how far that
 * chapter's visual is built. `built(i)` is the build level of chapter i:
 * 1 for chapters already passed, 0 for chapters still ahead.
 */
export function chapterState(progress) {
  const p = clamp01(Number.isFinite(progress) ? progress : 0)
  const chapter = Math.min(CHAPTER_COUNT - 1, Math.floor(p * CHAPTER_COUNT))
  const sub = clamp01(p * CHAPTER_COUNT - chapter)
  const current = Math.min(1, sub / BUILD_SHARE)
  return {
    chapter,
    sub,
    built: (i) => (i < chapter ? 1 : i > chapter ? 0 : current)
  }
}

/** Whether item `index` of `count` is revealed at build level `built`. */
export function revealed(built, index, count, span = 0.92) {
  return built >= ((index + 0.5) / count) * span
}

/** Progress value that lands in the middle of chapter `index`. */
export function chapterTarget(index) {
  return (index + 0.6) / CHAPTER_COUNT
}

export const CHAPTERS = [
  {
    key: 'data',
    label: 'Market data',
    kicker: 'Market data & brief',
    title: 'It starts with what you already have.',
    body: 'Drop in market research, a campaign brief, survey results. SimSend reads them the way an analyst would: who your customers are, who your competitors are, who talks about you.'
  },
  {
    key: 'graph',
    label: 'Knowledge graph',
    kicker: 'Knowledge graph',
    title: 'Then it maps your market.',
    body: 'Every person, brand, outlet and relationship it finds becomes part of a knowledge graph. That graph is the world your simulation runs in.'
  },
  {
    key: 'talk',
    label: 'Conversations',
    kicker: 'Simulation',
    title: 'Then the market starts talking.',
    body: 'Each entity becomes a persona with a profile and a memory. They post, reply, like and search on two simulated platforms, hour by simulated hour.'
  },
  {
    key: 'report',
    label: 'Report',
    kicker: 'Report',
    title: 'You get a report you can check.',
    body: 'The report agent reads the action log and writes up what happened, with what was observed and what is projected labelled separately.'
  },
  {
    key: 'ask',
    label: 'Follow-up',
    kicker: 'Follow-up',
    title: 'Then ask anything.',
    body: 'Ask the report agent to dig deeper, or interview any persona about why they reacted the way they did.'
  }
]

// Entities highlighted in the documents, in reveal order.
export const FOUND_ENTITIES = [
  'Students',
  "Int'l students",
  'Pedaalpas',
  'Stadsrijder',
  'Sanne Bakker',
  'Student paper',
  'Young professionals'
]

// Knowledge graph. x is 0..100 across, y is 0..60 down (the box is 5:3), in
// reveal order. kind: brand | segment | competitor | media | partner | detail
export const GRAPH_NODES = [
  { id: 'v', label: 'Velora', x: 50, y: 30, kind: 'brand' },
  { id: 'st', label: 'Students', x: 28, y: 17, kind: 'segment' },
  { id: 'in', label: "Int'l students", x: 18, y: 38, kind: 'segment' },
  { id: 'yp', label: 'Young professionals', x: 36, y: 50, kind: 'segment' },
  { id: 'ot', label: 'Commuters 35+', x: 66, y: 55, kind: 'segment' },
  { id: 'pp', label: 'Pedaalpas', x: 78, y: 13, kind: 'competitor' },
  { id: 'sr', label: 'Stadsrijder', x: 86, y: 33, kind: 'competitor' },
  { id: 'sp', label: 'Student paper', x: 48, y: 6, kind: 'media' },
  { id: 'rd', label: 'Utrecht subreddit', x: 12, y: 16, kind: 'media' },
  { id: 'sb', label: 'Sanne Bakker', x: 74, y: 43, kind: 'partner' },
  { id: 'cl', label: 'Classic plan', x: 38, y: 27, kind: 'detail' },
  { id: 'ep', label: 'E plan', x: 46, y: 41, kind: 'detail' },
  { id: 'vc', label: 'Velora Care', x: 61, y: 22, kind: 'detail' },
  { id: 'tf', label: 'Theft fee', x: 53, y: 55, kind: 'detail' },
  { id: 'pr', label: '2025 price rise', x: 26, y: 5, kind: 'detail' },
  { id: 'mv', label: 'CEO Mark Visser', x: 64, y: 7, kind: 'detail' },
  { id: 'ca', label: 'Campus ambassadors', x: 18, y: 55, kind: 'detail' },
  { id: 'se', label: 'Shared e-bikes', x: 91, y: 51, kind: 'detail' },
  { id: 'sh', label: 'Second-hand bikes', x: 92, y: 17, kind: 'detail' }
]

export const GRAPH_EDGES = [
  ['v', 'st'], ['v', 'in'], ['v', 'yp'], ['v', 'ot'], ['v', 'pp'], ['v', 'sr'], ['v', 'sp'], ['v', 'sb'],
  ['v', 'vc'], ['v', 'cl'], ['v', 'ep'], ['v', 'mv'], ['st', 'cl'], ['in', 'cl'], ['yp', 'ep'], ['ot', 'ep'],
  ['pp', 'sr'], ['sr', 'st'], ['sp', 'st'], ['rd', 'st'], ['rd', 'pr'], ['sp', 'pr'], ['sb', 'yp'], ['vc', 'tf'],
  ['tf', 'yp'], ['ca', 'st'], ['ca', 'in'], ['se', 'yp'], ['sh', 'st'], ['pp', 'sp']
]

// The graph box is 100 x 60 units, so these are percentages of its width.
export function edgeGeometry(a, b) {
  const dx = b.x - a.x
  const dy = b.y - a.y
  return {
    left: a.x,
    top: (a.y / 60) * 100,
    length: Math.hypot(dx, dy),
    angle: (Math.atan2(dy, dx) * 180) / Math.PI
  }
}

// Simulation feed, in the order it appears. Hours are simulated hours.
export const SIM_HOURS_SHOWN = 31
export const SIM_EVENTS = [
  { col: 'feed', h: 2, who: 'Sanne Bakker', role: 'Influencer', initials: 'SB', action: 'Post', tone: 'dark', text: "Honest Q&A: yes, my Velora gets more expensive in December. Here's what I get for it." },
  { col: 'feed', h: 5, who: 'Lotte M.', role: 'Student', initials: 'LM', action: 'Post', tone: 'light', text: 'ok they gave 5 weeks notice AND explained why. last time it was 7 days. this is better' },
  { col: 'forum', h: 7, who: 'u/fietsfan_utrecht', kind: 'thread', text: 'Velora raising prices AGAIN?' },
  { col: 'forum', h: 9, who: 'Arjun R.', kind: 'reply', text: 'Was the email only in Dutch? Does the lock cover September joiners?' },
  { col: 'forum', h: 11, who: 'Lotte M.', kind: 'reply', text: 'at least students keep the old price till 2027' },
  { col: 'feed', h: 14, who: 'Pedaalpas', role: 'Competitor', initials: 'PP', action: 'Post', tone: 'blue', text: "Hearing some bikes are getting more expensive in December. Ours aren't. Just saying." },
  { col: 'forum', h: 18, who: 'Student paper', kind: 'activity', text: 'searched “Velora price 2025”' },
  { col: 'feed', h: 20, who: 'Stadsrijder', role: 'Competitor', initials: 'SR', action: 'Post', tone: 'blue', text: 'Price going up somewhere? Switch to us. First month on the house.' },
  { col: 'feed', h: 22, who: 'Daan K.', role: 'Young pro', initials: 'DK', action: 'Like', tone: 'light', text: "Liked Velora's post about dropping the theft fee" }
]

export const REPORT_BARS = [
  { label: "Int'l students", n: 11 },
  { label: 'Students', n: 9 },
  { label: 'Young professionals', n: 5 },
  { label: 'Competitors', n: 3 }
]

export const CHAT = [
  { who: 'You → report agent', kind: 'me', text: 'Which segment should we talk to first?' },
  { who: 'Report agent', kind: 'them', text: 'International students. 11 of their replies asked about the email language or the price lock, and none got an answer in the simulated window.' },
  { who: 'You → Arjun R.', kind: 'me', text: 'Are you thinking of cancelling?' },
  { who: 'Arjun R. · interview', kind: 'them', text: "Maybe. It's not the €2.45. Nobody answered whether I'm covered. If Stadsrijder is cheaper and I don't get the lock, why stay?" },
  { who: 'Check', kind: 'check', text: 'Consistent with the action log: 3 replies from Arjun, no answer from Velora.' }
]
