<template>
  <section
    id="story"
    ref="storyEl"
    class="story"
    aria-label="How SimSend works, step by step"
  >
    <div class="stage" :class="`theme-${current.key}`">
      <!-- Chapter rail -->
      <div class="wrap rail-wrap">
        <ol class="rail">
          <li v-for="(c, i) in CHAPTERS" :key="c.key">
            <button
              type="button"
              class="rail-btn"
              :class="{ active: i === state.chapter }"
              :aria-current="i === state.chapter ? 'step' : undefined"
              @click="goTo(i)"
            >
              <span class="rail-track"><span class="rail-fill" :style="{ width: `${railFill(i) * 100}%` }"></span></span>
              <span class="rail-text"><b>0{{ i + 1 }}</b><span class="rail-label">{{ c.label }}</span></span>
            </button>
          </li>
        </ol>
      </div>

      <div class="wrap content">
        <!-- Chapter copy -->
        <div class="copy">
          <div
            v-for="(c, i) in CHAPTERS"
            :key="c.key"
            class="copy-layer"
            :class="layerClass(i)"
            :aria-hidden="i !== state.chapter"
          >
            <span class="kicker">0{{ i + 1 }} / 0{{ CHAPTERS.length }} · {{ c.kicker }}</span>
            <h2>{{ c.title }}</h2>
            <p>{{ c.body }}</p>
          </div>
        </div>

        <!-- Chapter visuals -->
        <div class="visual">
          <!-- 01 Documents -->
          <div class="vis-layer" :class="layerClass(0)" :aria-hidden="state.chapter !== 0">
            <div class="docs">
              <div class="sheets">
                <div class="sheet tilt-left">
                  <div class="sheet-name">velora_market_and_customer_data.md</div>
                  <strong>Customer base</strong>
                  <p><mark :class="{ on: hl(0) }">Students (18–25)</mark> make up 46% of subscribers and are the most price-sensitive. <mark :class="{ on: hl(1) }">International students</mark> are 15%, with the shortest average tenure.</p>
                  <strong>Competitors</strong>
                  <p><mark :class="{ on: hl(2) }">Pedaalpas</mark> is the market leader, known for fast, witty replies. <mark :class="{ on: hl(3) }">Stadsrijder</mark> is the budget challenger at €14.95.</p>
                </div>
                <div class="sheet tilt-right">
                  <div class="sheet-name">velora_campaign_brief.md</div>
                  <strong>Timeline</strong>
                  <p>Partner influencer <mark :class="{ on: hl(4) }">Sanne Bakker</mark> posts an honest Q&amp;A on the price. Press release to local media and <mark :class="{ on: hl(5) }">student newspapers</mark>.</p>
                  <strong>Target audiences</strong>
                  <p>Existing subscribers, and <mark :class="{ on: hl(6) }">young professionals</mark> unhappy with a competitor's repair times.</p>
                </div>
              </div>
              <div class="prompt"><span class="accent">&gt;_</span> Simulate how students, international students, young professionals, competitors and local media react in the first week after the price announcement.</div>
              <div class="found">
                <span class="found-count">Entities found: {{ foundCount }}</span>
                <span
                  v-for="(label, i) in FOUND_ENTITIES"
                  :key="label"
                  class="chip reveal"
                  :class="{ on: hl(i) }"
                >{{ label }}</span>
              </div>
            </div>
          </div>

          <!-- 02 Knowledge graph -->
          <div class="vis-layer" :class="layerClass(1)" :aria-hidden="state.chapter !== 1">
            <div class="graph-panel">
              <div class="graph-meta">
                <span><b>{{ graph.nodeCount }}</b> entities · <b>{{ graph.edgeCount }}</b> relationships</span>
                <span class="legend">
                  <span><i class="dot brand"></i>Your brand</span>
                  <span><i class="dot segment"></i>Segment</span>
                  <span><i class="dot competitor"></i>Competitor</span>
                  <span><i class="dot media"></i>Media</span>
                </span>
              </div>
              <div
                class="graph"
                role="img"
                aria-label="Knowledge graph of the Velora market: segments, competitors, media and partners connected to Velora"
              >
                <span
                  v-for="(e, i) in graph.edges"
                  :key="`e${i}`"
                  class="edge"
                  :class="{ on: e.on, hot: e.hot }"
                  :style="e.style"
                ></span>
                <span
                  v-for="n in graph.nodes"
                  :key="n.id"
                  class="node"
                  :class="[n.kind, { on: n.on }]"
                  :style="n.style"
                >
                  <i class="node-dot"></i>
                  <span class="node-label">{{ n.label }}</span>
                </span>
              </div>
            </div>
          </div>

          <!-- 03 Conversations -->
          <div class="vis-layer" :class="layerClass(2)" :aria-hidden="state.chapter !== 2">
            <div class="platforms">
              <div class="platforms-meta">
                <span class="live"><i class="live-dot"></i>Live · simulated hour {{ sim.hour }} / 168</span>
                <span>{{ sim.posts }} posts and replies so far</span>
              </div>
              <div class="columns">
                <div class="column feed">
                  <div class="column-head">Feed</div>
                  <div
                    v-for="p in sim.feed"
                    :key="p.h"
                    class="post reveal"
                    :class="{ on: p.on }"
                  >
                    <span class="avatar" :class="p.tone" aria-hidden="true">{{ p.initials }}</span>
                    <span class="post-body">
                      <span class="post-head"><b>{{ p.who }}</b><span class="meta">{{ p.role }} · h{{ p.h }}</span><span class="action">{{ p.action }}</span></span>
                      <span class="post-text">{{ p.text }}</span>
                    </span>
                  </div>
                </div>
                <div class="column forum">
                  <div class="column-head">Forum</div>
                  <div
                    v-for="p in sim.forum"
                    :key="p.h"
                    class="thread-item reveal"
                    :class="[p.kind, { on: p.on }]"
                  >
                    <span class="post-head"><b>{{ p.who }}</b><span class="meta">h{{ p.h }}</span></span>
                    <span class="thread-text">{{ p.text }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 04 Report -->
          <div class="vis-layer" :class="layerClass(3)" :aria-hidden="state.chapter !== 3">
            <article class="report">
              <div class="report-meta"><span>SimSend report · velora-price-change</span><span>hours 1–31 of 168 simulated</span></div>
              <h3 class="reveal" :class="{ on: rep(0) }">International students are the most likely to switch</h3>
              <p class="reveal" :class="{ on: rep(1) }">Students mostly welcomed the five weeks' notice and the price lock. International students replied with questions instead, and none got an answer from Velora in the simulated window.</p>
              <div class="finding reveal" :class="{ on: rep(2) }"><span class="tag observed">Observed</span><span>11 replies from international students asked about the email language or the price lock.</span></div>
              <div class="finding reveal" :class="{ on: rep(3) }"><span class="tag observed">Observed</span><span>Pedaalpas posted a jab at hour 14; Stadsrijder followed with a switch offer at hour 20.</span></div>
              <div class="finding reveal" :class="{ on: rep(4) }"><span class="tag projection">Projection</span><span>If the questions stay unanswered, Stadsrijder's offer is the likely landing place for this segment in days 2–7.</span></div>
              <div class="bars reveal" :class="{ on: rep(5) }">
                <span class="bars-title">Posts and replies by segment</span>
                <div v-for="b in REPORT_BARS" :key="b.label" class="bar-row">
                  <span>{{ b.label }}</span>
                  <span class="bar-track"><span class="bar" :class="{ top: b.n === maxBar }" :style="{ width: rep(5) ? `${(b.n / maxBar) * 100}%` : '0%' }"></span></span>
                  <span class="bar-n">{{ b.n }}</span>
                </div>
              </div>
            </article>
          </div>

          <!-- 05 Follow-up -->
          <div class="vis-layer" :class="layerClass(4)" :aria-hidden="state.chapter !== 4">
            <div class="chat">
              <div class="chat-tabs">
                <span class="chat-tab active">Report agent</span>
                <span class="chat-tab">Interview a persona</span>
              </div>
              <div class="chat-log">
                <div
                  v-for="(m, i) in CHAT"
                  :key="i"
                  class="bubble reveal"
                  :class="[m.kind, { on: chat(i) }]"
                >
                  <span class="bubble-who">{{ m.who }}</span>
                  <span>{{ m.text }}</span>
                </div>
              </div>
              <div class="chat-input" aria-hidden="true">
                <span class="fake-input">Ask a follow-up…</span>
                <span class="fake-btn">Ask</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  CHAPTERS,
  CHAT,
  FOUND_ENTITIES,
  GRAPH_EDGES,
  GRAPH_NODES,
  REPORT_BARS,
  SIM_EVENTS,
  SIM_HOURS_SHOWN,
  chapterState,
  chapterTarget,
  edgeGeometry,
  revealed
} from './story'

const storyEl = ref(null)
const progress = ref(0)

const state = computed(() => chapterState(progress.value))
const current = computed(() => CHAPTERS[state.value.chapter])

const layerClass = (i) => ({
  active: i === state.value.chapter,
  before: i < state.value.chapter,
  after: i > state.value.chapter
})

const railFill = (i) => {
  if (i < state.value.chapter) return 1
  return i === state.value.chapter ? state.value.sub : 0
}

// 01 documents
const hl = (i) => revealed(state.value.built(0), i, FOUND_ENTITIES.length)
const foundCount = computed(() => FOUND_ENTITIES.filter((_, i) => hl(i)).length)

// 02 graph: nodes come in over the first 80% of the build
const graph = computed(() => {
  const built = state.value.built(1)
  const byId = {}
  const nodes = GRAPH_NODES.map((n, i) => {
    const on = revealed(built, i, GRAPH_NODES.length, 0.8)
    byId[n.id] = { ...n, on }
    return {
      ...n,
      on,
      style: { left: `${n.x}%`, top: `${(n.y / 60) * 100}%` }
    }
  })
  let edgeCount = 0
  const edges = GRAPH_EDGES.map(([a, b]) => {
    const g = edgeGeometry(byId[a], byId[b])
    const on = byId[a].on && byId[b].on
    if (on) edgeCount += 1
    return {
      on,
      hot: a === 'v',
      style: {
        left: `${g.left}%`,
        top: `${g.top}%`,
        width: `${g.length}%`,
        '--angle': `${g.angle}deg`
      }
    }
  })
  return { nodes, edges, nodeCount: nodes.filter((n) => n.on).length, edgeCount }
})

// 03 conversations
const sim = computed(() => {
  const built = state.value.built(2)
  const events = SIM_EVENTS.map((e, i) => ({ ...e, on: revealed(built, i, SIM_EVENTS.length) }))
  const shown = events.filter((e) => e.on)
  // The clock never runs behind the newest visible event.
  const latest = shown.length ? shown[shown.length - 1].h : 0
  return {
    feed: events.filter((e) => e.col === 'feed'),
    forum: events.filter((e) => e.col === 'forum'),
    hour: shown.length ? Math.max(latest, Math.round(built * SIM_HOURS_SHOWN)) : 0,
    posts: shown.filter((e) => e.kind !== 'activity' && e.action !== 'Like').length
  }
})

// 04 report
const rep = (i) => revealed(state.value.built(3), i, 6, 0.9)
const maxBar = Math.max(...REPORT_BARS.map((b) => b.n))

// 05 follow-up
const chat = (i) => revealed(state.value.built(4), i, CHAT.length)

// Scroll tracking
let frame = 0
const scrollRange = () => {
  const el = storyEl.value
  return el ? el.getBoundingClientRect().height - window.innerHeight : 0
}
const measure = () => {
  frame = 0
  const el = storyEl.value
  const range = scrollRange()
  if (!el || range <= 0) return
  const p = Math.max(0, Math.min(1, -el.getBoundingClientRect().top / range))
  if (Math.abs(p - progress.value) > 0.001) progress.value = p
}
const onScroll = () => {
  if (!frame) frame = requestAnimationFrame(measure)
}

const prefersReducedMotion = () =>
  typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

const goTo = (i) => {
  const el = storyEl.value
  const range = scrollRange()
  if (!el || range <= 0) {
    progress.value = chapterTarget(i)
    return
  }
  window.scrollTo({
    top: window.scrollY + el.getBoundingClientRect().top + chapterTarget(i) * range,
    behavior: prefersReducedMotion() ? 'auto' : 'smooth'
  })
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('resize', onScroll)
  measure()
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
  window.removeEventListener('resize', onScroll)
  if (frame) cancelAnimationFrame(frame)
})
</script>

<style scoped>
.story {
  /* One viewport of sticky stage plus one viewport of scroll per chapter. */
  height: 600vh;
  height: 600svh;
  position: relative;
  background: var(--ink);
}

.stage {
  position: sticky;
  top: 0;
  height: 100vh;
  height: 100svh;
  overflow: hidden;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  background: var(--stage-bg);
  color: var(--stage-fg);
  transition: background-color 0.6s ease, color 0.6s ease;
}

.theme-data { --stage-bg: var(--paper); --stage-fg: var(--ink); --rail-fill: var(--orange); }
.theme-graph { --stage-bg: var(--ink); --stage-fg: var(--white); --rail-fill: var(--orange); }
.theme-talk { --stage-bg: var(--white); --stage-fg: var(--ink); --rail-fill: var(--orange); }
.theme-report { --stage-bg: var(--ink-2); --stage-fg: var(--white); --rail-fill: var(--orange); }
.theme-ask { --stage-bg: var(--orange); --stage-fg: var(--ink); --rail-fill: var(--ink); }

.wrap {
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
  padding-left: clamp(16px, 4vw, 40px);
  padding-right: clamp(16px, 4vw, 40px);
}

/* Rail */
.rail-wrap { padding-top: 20px; }
.rail {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}
.rail-btn {
  width: 100%;
  min-height: 44px;
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-align: left;
  font-family: var(--mono);
  font-size: 12px;
  letter-spacing: 0.5px;
  opacity: 0.6;
  transition: opacity 0.3s;
}
.rail-btn.active, .rail-btn:hover { opacity: 1; }
.rail-btn:focus-visible { outline: 2px solid currentColor; outline-offset: 4px; }
.rail-track {
  display: block;
  position: relative;
  height: 3px;
  background: color-mix(in srgb, currentColor 22%, transparent);
  overflow: hidden;
}
.rail-fill {
  position: absolute;
  inset: 0 auto 0 0;
  background: var(--rail-fill);
  transition: width 0.15s linear;
}
.rail-text { display: flex; gap: 8px; align-items: baseline; }

/* Layout */
.content {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(0, 1.75fr);
  gap: 56px;
  padding-top: 24px;
  padding-bottom: 32px;
  min-height: 0;
}
.copy, .visual { position: relative; min-height: 0; }

.copy-layer, .vis-layer {
  position: absolute;
  inset: 0;
  transition: opacity 0.5s ease, transform 0.5s ease, visibility 0s linear 0.5s;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
}
.copy-layer.active, .vis-layer.active {
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
  transform: none;
  transition: opacity 0.5s ease, transform 0.5s ease, visibility 0s;
}
.copy-layer.before { transform: translateY(-24px); }
.copy-layer.after { transform: translateY(24px); }
.vis-layer:not(.active) { transform: scale(0.97); }

.copy-layer {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 20px;
}
.kicker {
  font-family: var(--mono);
  font-size: 13px;
  letter-spacing: 1px;
  text-transform: uppercase;
  opacity: 0.75;
}
.copy-layer h2 {
  font-size: clamp(32px, 3.4vw, 48px);
  line-height: 1.05;
  font-weight: 600;
  letter-spacing: -0.02em;
}
.copy-layer p {
  font-size: 18px;
  line-height: 1.6;
  opacity: 0.85;
  max-width: 440px;
}

.vis-layer {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Shared reveal */
.reveal {
  opacity: 0;
  transform: translateY(12px);
  transition: opacity 0.45s ease, transform 0.45s ease;
}
.reveal.on { opacity: 1; transform: none; }

/* 01 Documents */
.docs { width: 100%; display: flex; flex-direction: column; gap: 16px; }
.sheets { display: flex; gap: 16px; }
.sheet {
  flex: 1 1 0;
  min-width: 0;
  background: var(--white);
  border: 1px solid var(--ink);
  box-shadow: 6px 6px 0 var(--ink);
  padding: 20px;
  font-size: 14px;
  line-height: 1.7;
  color: #262626;
}
.tilt-left { transform: rotate(-1deg); }
.tilt-right { transform: rotate(1deg); }
.sheet strong { font-size: 15px; color: var(--ink); }
.sheet p { margin: 4px 0 12px; }
.sheet p:last-child { margin-bottom: 0; }
.sheet-name {
  font-family: var(--mono);
  font-size: 11px;
  color: #525252;
  border-bottom: 1px solid #E5E5E5;
  padding-bottom: 8px;
  margin-bottom: 10px;
  overflow-wrap: anywhere;
}
mark {
  background: transparent;
  color: inherit;
  padding: 1px 3px;
  transition: background-color 0.35s ease;
}
mark.on { background: var(--orange); color: var(--ink); }
.prompt {
  background: var(--ink);
  color: #E5E5E5;
  font-family: var(--mono);
  font-size: 13px;
  line-height: 1.6;
  padding: 16px 18px;
}
.accent { color: var(--orange); }
.found {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  min-height: 34px;
}
.found-count {
  font-family: var(--mono);
  font-size: 12px;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: #404040;
}
.chip {
  font-family: var(--mono);
  font-size: 12px;
  padding: 4px 8px;
  border: 1px solid var(--ink);
  background: var(--white);
  color: var(--ink);
}

/* 02 Graph */
.graph-panel { width: 100%; display: flex; flex-direction: column; gap: 12px; align-items: center; }
.graph-meta {
  width: min(100%, calc((100svh - 240px) * 5 / 3));
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px;
  font-family: var(--mono);
  font-size: 12px;
  color: #A3A3A3;
}
.graph-meta b { color: var(--white); font-weight: 500; }
.legend { display: flex; flex-wrap: wrap; gap: 14px; }
.legend > span { display: inline-flex; align-items: center; gap: 6px; }
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }
.dot.brand { background: var(--orange); }
.dot.segment { background: var(--white); }
.dot.competitor { background: var(--blue); }
.dot.media { border: 2px solid var(--white); }
.graph {
  position: relative;
  width: min(100%, calc((100svh - 240px) * 5 / 3));
  aspect-ratio: 5 / 3;
  border: 1px solid #262626;
  background: #0F0F0F;
  overflow: hidden;
}
.edge {
  position: absolute;
  height: 1px;
  background: rgba(255, 255, 255, 0.28);
  transform-origin: 0 50%;
  transform: rotate(var(--angle)) scaleX(0);
  transition: transform 0.6s ease;
}
.edge.hot { background: rgba(255, 69, 0, 0.55); }
.edge.on { transform: rotate(var(--angle)) scaleX(1); }
.node {
  --size: 9px;
  position: absolute;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  transform: translate(-50%, calc(var(--size) / -2));
}
.node-dot {
  display: block;
  width: var(--size);
  height: var(--size);
  border-radius: 50%;
  background: #737373;
  transform: scale(0);
  transition: transform 0.45s cubic-bezier(0.3, 1.6, 0.5, 1);
}
.node-label {
  font-family: var(--mono);
  font-size: 10px;
  white-space: nowrap;
  color: #A3A3A3;
  opacity: 0;
  transition: opacity 0.4s ease 0.1s;
}
.node.on .node-dot { transform: scale(1); }
.node.on .node-label { opacity: 1; }
.node.brand { --size: 26px; }
.node.brand .node-dot { background: var(--orange); box-shadow: 0 0 0 8px rgba(255, 69, 0, 0.22); }
.node.brand .node-label { color: var(--white); font-weight: 700; font-size: 13px; }
.node.segment, .node.competitor { --size: 16px; }
.node.segment .node-dot { background: var(--white); }
.node.competitor .node-dot { background: var(--blue); }
.node.media, .node.partner { --size: 14px; }
.node.media .node-dot { background: transparent; border: 2px solid var(--white); }
.node.partner .node-dot { background: transparent; border: 2px dashed var(--orange); }
.node.segment .node-label,
.node.competitor .node-label,
.node.media .node-label,
.node.partner .node-label { color: var(--white); font-size: 11px; }

/* 03 Conversations */
.platforms { width: 100%; height: 100%; display: flex; flex-direction: column; gap: 12px; }
.platforms-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-family: var(--mono);
  font-size: 12px;
  color: #404040;
}
.live { display: flex; align-items: center; gap: 8px; color: var(--ink); text-transform: uppercase; }
.live-dot {
  width: 8px;
  height: 8px;
  background: var(--orange);
  animation: blink 1.4s ease-in-out infinite;
}
.columns { flex: 1; min-height: 0; display: flex; gap: 16px; }
.column {
  min-width: 0;
  border: 1px solid var(--ink);
  background: var(--white);
  overflow: hidden;
}
.column.feed { flex: 3 1 0; }
.column.forum { flex: 2 1 0; }
.column-head {
  padding: 10px 14px;
  border-bottom: 1px solid var(--ink);
  font-family: var(--mono);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}
.post {
  display: flex;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid #E5E5E5;
}
.avatar {
  width: 32px;
  height: 32px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--mono);
  font-weight: 700;
  font-size: 11px;
}
.avatar.light { background: #E5E5E5; color: var(--ink); }
.avatar.dark { background: var(--ink); color: var(--white); }
.avatar.blue { background: var(--blue); color: var(--ink); }
.post-body { display: flex; flex-direction: column; gap: 4px; min-width: 0; flex: 1; }
.post-head { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 13px; }
.meta { font-family: var(--mono); font-size: 10px; color: #525252; text-transform: uppercase; }
.action {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 10px;
  text-transform: uppercase;
  background: var(--ink);
  color: var(--white);
  padding: 1px 5px;
}
.post-text { font-size: 14px; line-height: 1.45; color: #262626; }
.thread-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 14px;
  border-bottom: 1px solid #E5E5E5;
}
.thread-item.reply, .thread-item.activity { margin-left: 14px; border-left: 2px solid #E5E5E5; }
.thread-item.thread .thread-text { font-size: 15px; font-weight: 700; line-height: 1.35; }
.thread-item.reply .thread-text { font-size: 14px; line-height: 1.45; color: #262626; }
.thread-item.activity .thread-text { font-family: var(--mono); font-size: 12px; color: #525252; }

/* 04 Report */
.report {
  width: 100%;
  max-width: 720px;
  max-height: 100%;
  overflow: hidden;
  background: var(--white);
  color: var(--ink);
  padding: clamp(20px, 3vw, 32px);
  display: flex;
  flex-direction: column;
  gap: 14px;
  box-shadow: 12px 12px 0 var(--orange);
}
.report-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px;
  font-family: var(--mono);
  font-size: 11px;
  color: #525252;
  text-transform: uppercase;
}
.report h3 { font-size: 24px; line-height: 1.25; font-weight: 600; }
.report > p { font-size: 15px; line-height: 1.6; color: #404040; }
.finding {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  font-size: 14px;
  line-height: 1.5;
  padding: 10px 12px;
  border: 1px solid #E5E5E5;
}
.tag {
  flex: none;
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  padding: 3px 6px;
}
.tag.observed { background: var(--ink); color: var(--white); }
.tag.projection { border: 1px dashed #525252; color: #404040; padding: 2px 5px; }
.bars { display: flex; flex-direction: column; gap: 8px; padding-top: 6px; }
.bars-title { font-family: var(--mono); font-size: 11px; color: #525252; text-transform: uppercase; }
.bar-row {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr) 28px;
  gap: 10px;
  align-items: center;
  font-size: 13px;
}
.bar-track { height: 10px; background: #F0F0F0; }
.bar { display: block; height: 10px; background: var(--ink); transition: width 0.7s ease; }
.bar.top { background: var(--orange); }
.bar-n { font-family: var(--mono); font-size: 12px; text-align: right; }

/* 05 Follow-up */
.chat {
  width: 100%;
  max-width: 680px;
  background: var(--white);
  color: var(--ink);
  border: 2px solid var(--ink);
  display: flex;
  flex-direction: column;
}
.chat-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 2px solid var(--ink);
  font-family: var(--mono);
  font-size: 12px;
}
.chat-tab { border: 1px solid var(--ink); padding: 3px 7px; }
.chat-tab.active { background: var(--ink); color: var(--white); }
.chat-log {
  padding: 18px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 320px;
}
.bubble {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 86%;
  padding: 10px 12px;
  font-size: 14px;
  line-height: 1.5;
}
.bubble.me { align-self: flex-end; background: var(--ink); color: var(--white); }
.bubble.them { align-self: flex-start; background: var(--paper); }
.bubble.check {
  align-self: flex-start;
  border: 1px dashed #525252;
  color: #262626;
  font-family: var(--mono);
  font-size: 12px;
}
.bubble-who { font-family: var(--mono); font-size: 10px; text-transform: uppercase; opacity: 0.75; }
.chat-input { display: flex; gap: 8px; padding: 12px 16px; border-top: 1px solid #D4D4D4; }
.fake-input {
  flex: 1;
  min-height: 44px;
  border: 1px solid #A3A3A3;
  padding: 0 12px;
  display: flex;
  align-items: center;
  color: #737373;
}
.fake-btn {
  min-height: 44px;
  padding: 0 18px;
  background: var(--ink);
  color: var(--white);
  font-weight: 600;
  display: flex;
  align-items: center;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}

/* Short screens: drop the prompt card and tighten the documents. */
@media (max-height: 760px) {
  .prompt { display: none; }
  .sheet { padding: 14px; font-size: 13px; line-height: 1.55; }
  .chat-log { min-height: 0; }
  .bars { display: none; }
}

/* Phones and narrow tablets: copy above the visual, simpler visuals. */
@media (max-width: 820px) {
  .content {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: 190px minmax(0, 1fr);
    gap: 12px;
    padding-top: 12px;
    padding-bottom: 16px;
  }
  .copy-layer { gap: 10px; justify-content: flex-end; }
  .copy-layer h2 { font-size: 28px; }
  .copy-layer p { font-size: 15px; }
  .rail-label { display: none; }
  .sheet.tilt-right, .prompt, .column.forum, .bars, .legend { display: none; }
  .node.detail .node-label { display: none; }
  .graph, .graph-meta { width: 100%; }
  .bar-row { grid-template-columns: 110px minmax(0, 1fr) 24px; }
  .chat-log { min-height: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .stage, .copy-layer, .vis-layer, .reveal, mark, .edge, .node-dot, .node-label, .bar, .rail-fill {
    transition: none !important;
  }
  .live-dot { animation: none; }
}
</style>
