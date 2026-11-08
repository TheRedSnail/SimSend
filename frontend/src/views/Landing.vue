<template>
  <div class="mk">
    <header class="nav-bar">
      <nav class="wrap nav" aria-label="Main">
        <a href="#top" class="brand" @click.prevent="jump('top')">
          <span class="brand-mark" aria-hidden="true"></span>SimSend
        </a>
        <div class="nav-links">
          <a href="#how" @click.prevent="jump('how')">How it works</a>
          <a href="#example" @click.prevent="jump('example')">Example</a>
          <a href="#signup" class="btn btn-primary btn-small" @click.prevent="cta('nav', 'signup')">Get early access</a>
        </div>
      </nav>
    </header>

    <main>
      <!-- Hero: a campaign, and the market reacting to it -->
      <section id="top" class="hero">
        <div class="wrap hero-inner">
          <div class="hero-copy">
            <h1>See how your market reacts before you launch.</h1>
            <p class="lede">
              Test a campaign, price change or launch on a simulated audience of your customers,
              competitors and press. See what they say, who pushes back, and what to fix.
            </p>
            <div class="ctas">
              <a href="#signup" class="btn btn-primary" @click.prevent="cta('hero', 'signup')">Get early access</a>
              <a href="#example" class="btn btn-quiet" @click.prevent="cta('hero-example', 'example')">See an example</a>
            </div>
          </div>

          <figure class="board" aria-label="Example: three simulated reactions to a price change">
            <div class="campaign">
              <span class="campaign-label">Your campaign</span>
              <strong>{{ CAMPAIGN.brand }}: {{ CAMPAIGN.title }}</strong>
              <span class="campaign-detail">{{ CAMPAIGN.detail }}</span>
            </div>

            <ol class="reactions">
              <li
                v-for="(r, i) in REACTIONS"
                :key="r.who"
                class="reaction"
                :style="{ '--i': i }"
              >
                <span class="avatar" :class="r.mood" aria-hidden="true">{{ r.initials }}</span>
                <div class="reaction-body">
                  <div class="reaction-head">
                    <b>{{ r.who }}</b>
                    <span class="reaction-role">{{ r.role }}</span>
                  </div>
                  <p>{{ r.text }}</p>
                  <span class="mood" :class="r.mood">{{ r.moodLabel }}</span>
                </div>
              </li>
            </ol>

            <div class="insight">
              <span>{{ INSIGHT.label }}</span>
              <strong>{{ INSIGHT.value }}</strong>
            </div>
          </figure>
        </div>
      </section>

      <!-- Benefits -->
      <section class="benefits">
        <div class="wrap benefits-inner">
          <h2 class="benefits-title">Find the problems while they're still cheap to fix.</h2>
          <ul class="benefit-list">
            <li v-for="b in BENEFITS" :key="b.title" class="benefit">
              <span class="benefit-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor"
                     stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path v-for="d in ICONS[b.icon].paths" :key="d" :d="d" />
                  <circle v-for="c in ICONS[b.icon].circles || []" :key="c.join()" :cx="c[0]" :cy="c[1]" :r="c[2]" />
                </svg>
              </span>
              <h3>{{ b.title }}</h3>
              <p>{{ b.body }}</p>
            </li>
          </ul>
        </div>
      </section>

      <!-- How it works -->
      <section id="how" class="how">
        <div class="wrap">
          <h2 class="section-title">From brief to answers in three steps.</h2>
          <ol class="steps">
            <li v-for="(s, i) in STEPS" :key="s.title" class="step">
              <span class="step-n" aria-hidden="true">{{ i + 1 }}</span>
              <h3>{{ s.title }}</h3>
              <p>{{ s.body }}</p>
            </li>
          </ol>
        </div>
      </section>

      <!-- Example result -->
      <section id="example" class="example">
        <div class="wrap">
          <h2 class="section-title">What a run tells you.</h2>
          <p class="section-sub">An example from a sample run: a bike subscription brand announcing a price change.</p>

          <article class="report">
            <div class="report-main">
              <span class="report-label">Main finding</span>
              <h3>{{ EXAMPLE.finding }}</h3>
              <p class="report-summary">{{ EXAMPLE.summary }}</p>
              <div class="next-step">
                <span class="report-label">Suggested next step</span>
                <p>{{ EXAMPLE.nextStep }}</p>
              </div>
            </div>

            <div class="report-side">
              <div class="bars">
                <span class="report-label">{{ EXAMPLE.barsTitle }}</span>
                <div v-for="b in EXAMPLE.bars" :key="b.label" class="bar-row">
                  <span class="bar-label">{{ b.label }}</span>
                  <span class="bar-track">
                    <span class="bar" :class="{ top: b.n === maxBar }" :style="{ width: `${(b.n / maxBar) * 100}%` }"></span>
                  </span>
                  <span class="bar-n">{{ b.n }}</span>
                </div>
              </div>

              <blockquote class="quote">
                <p>“{{ EXAMPLE.quote.text }}”</p>
                <footer>{{ EXAMPLE.quote.who }}, when asked why</footer>
              </blockquote>
            </div>
          </article>
        </div>
      </section>

      <!-- Use cases -->
      <section class="uses">
        <div class="wrap uses-inner">
          <h2 class="section-title">Use it before you say something to your market.</h2>
          <ul class="chips">
            <li v-for="u in USE_CASES" :key="u">{{ u }}</li>
          </ul>
        </div>
      </section>

      <!-- Sign-up -->
      <section id="signup" class="signup">
        <div class="wrap signup-inner">
          <div class="signup-copy">
            <h2>Be one of the first marketers to try it.</h2>
            <p>
              SimSend is in early access. Leave your details and we'll set you up with a workspace and a
              sample brief, so your first test takes minutes.
            </p>
            <ul class="points">
              <li>Works from the briefs and research you already have</li>
              <li>No technical setup on your side</li>
              <li>Every finding links back to what the audience actually said</li>
            </ul>
          </div>
          <SignupForm class="signup-form" />
        </div>
      </section>
    </main>

    <footer class="footer">
      <div class="wrap footer-inner">
        <span>SimSend</span>
        <span>Examples on this page come from an illustrative sample run.</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import analytics from '../analytics'
import SignupForm from '../components/landing/SignupForm.vue'
import {
  BENEFITS,
  CAMPAIGN,
  EXAMPLE,
  INSIGHT,
  REACTIONS,
  STEPS,
  USE_CASES
} from '../components/landing/content'

// 24x24 stroke icons for the benefit list.
const ICONS = {
  alert: { paths: ['M12 3.5 2.5 20h19L12 3.5z', 'M12 10v4.5', 'M12 17.2v.1'] },
  sliders: {
    paths: ['M4 7h8', 'M16 7h4', 'M4 17h2', 'M10 17h10'],
    circles: [[14, 7, 2], [8, 17, 2]]
  },
  quote: { paths: ['M4 5h16v11H10l-4.5 4V16H4z', 'M8.5 9.5h7', 'M8.5 12.5h4.5'] },
  doc: { paths: ['M7 3h7l5 5v13H7z', 'M14 3v5h5', 'M10 13h6', 'M10 17h4'] }
}

const maxBar = Math.max(...EXAMPLE.bars.map((b) => b.n))

const jump = (id) => {
  const el = document.getElementById(id)
  if (!el) return
  const reduce = typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
  if (window.location.hash !== `#${id}`) history.replaceState(history.state, '', `#${id}`)
}

// Main call-to-action buttons: record which one was used, then scroll.
const cta = (button, target) => {
  analytics.track('cta-click', { button })
  jump(target)
}

let previousTitle = ''
onMounted(() => {
  previousTitle = document.title
  document.title = 'SimSend · See how your market reacts before you launch'
  analytics.load()
  analytics.pageview()
  const id = window.location.hash.slice(1)
  if (id) requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView())
})
onBeforeUnmount(() => {
  document.title = previousTitle
})
</script>

<style scoped>
.mk {
  /* Tokens. SignupForm reads --white, --ink, --orange and --sans. */
  --white: #FFFFFF;
  --ink: #1A1D24;
  --ink-soft: #4A505C;
  --line: #DDE2E9;
  --tint: #EEF3F9;
  --orange: #FF4500;
  --orange-text: #C2410C;
  --positive: #1A7F52;
  --positive-bg: #E3F4EC;
  --worried: #8F5300;
  --worried-bg: #FDF0D9;
  --rival: #2F5BD3;
  --rival-bg: #E6EDFC;
  --sans: 'Space Grotesk', system-ui, sans-serif;
  font-family: var(--sans);
  color: var(--ink);
  background: var(--white);
  min-width: 0;
}

.wrap {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding-left: clamp(16px, 4vw, 40px);
  padding-right: clamp(16px, 4vw, 40px);
}

a { color: inherit; }
a:focus-visible { outline: 3px solid var(--orange); outline-offset: 3px; border-radius: 4px; }

h1, h2, h3 { font-weight: 600; letter-spacing: -0.02em; }
p { line-height: 1.6; }

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 52px;
  padding: 0 24px;
  border-radius: 12px;
  font-size: 17px;
  font-weight: 600;
  text-decoration: none;
  transition: background-color 0.2s, border-color 0.2s;
}
.btn-primary { background: var(--orange); color: var(--ink); }
.btn-primary:hover { background: #FF6A33; }
.btn-quiet { border: 1.5px solid #B8BFCA; color: var(--ink); }
.btn-quiet:hover { border-color: var(--ink); }
.btn-small { min-height: 44px; padding: 0 18px; font-size: 15px; }

/* Nav */
.nav-bar { border-bottom: 1px solid var(--line); background: var(--white); }
.nav {
  min-height: 68px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 32px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  font-weight: 700;
  font-size: 20px;
  letter-spacing: -0.01em;
}
.brand-mark { width: 14px; height: 14px; border-radius: 4px; background: var(--orange); }
.nav-links { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 28px; font-size: 15px; }
.nav-links a:not(.btn) { color: var(--ink-soft); text-decoration: none; padding: 12px 0; }
.nav-links a:not(.btn):hover { color: var(--ink); }

/* Hero */
.hero { background: var(--tint); }
.hero-inner {
  padding-top: clamp(40px, 7vw, 96px);
  padding-bottom: clamp(48px, 7vw, 96px);
  display: flex;
  flex-wrap: wrap;
  gap: 48px 64px;
  align-items: flex-start;
}
.hero-copy { flex: 1 1 420px; min-width: 0; display: flex; flex-direction: column; gap: 24px; padding-top: 8px; }
h1 { font-size: clamp(40px, 5.4vw, 72px); line-height: 1.02; letter-spacing: -0.035em; max-width: 12ch; }
.lede { font-size: clamp(18px, 1.6vw, 20px); color: var(--ink-soft); max-width: 34em; }
.ctas { display: flex; flex-wrap: wrap; gap: 12px; }

/* The board: one campaign, three reactions coming off it */
.board {
  flex: 1 1 480px;
  min-width: 0;
  margin: 0;
  position: relative;
  padding-bottom: 40px;
}
.campaign {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--ink);
  color: var(--white);
  border-radius: 18px;
  padding: 20px 22px;
  box-shadow: 0 18px 40px -18px rgba(26, 29, 36, 0.55);
}
.campaign-label { font-size: 14px; color: #FFB08F; }
.campaign strong { font-size: 21px; font-weight: 600; letter-spacing: -0.01em; }
.campaign-detail { font-size: 15px; color: #C9CDD4; }

.reactions {
  list-style: none;
  margin: 0 0 0 28px;
  padding: 18px 0 0 26px;
  border-left: 2px solid #C9D3E0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.reaction {
  position: relative;
  display: flex;
  gap: 12px;
  background: var(--white);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px;
  box-shadow: 0 10px 24px -16px rgba(26, 29, 36, 0.35);
  animation: arrive 0.5s cubic-bezier(0.2, 0.7, 0.3, 1) both;
  animation-delay: calc(0.35s + var(--i) * 0.45s);
}
/* Tick joining each reaction to the campaign's line */
.reaction::before {
  content: '';
  position: absolute;
  left: -27px;
  top: 30px;
  width: 26px;
  height: 2px;
  background: #C9D3E0;
}
.avatar {
  width: 40px;
  height: 40px;
  flex: none;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
}
.avatar.positive { background: var(--positive-bg); color: var(--positive); }
.avatar.worried { background: var(--worried-bg); color: var(--worried); }
.avatar.rival { background: var(--rival-bg); color: var(--rival); }
.reaction-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; align-items: flex-start; }
.reaction-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 8px; font-size: 15px; }
.reaction-role { font-size: 13px; color: var(--ink-soft); }
.reaction-body p { font-size: 15px; line-height: 1.5; }
.mood {
  font-size: 13px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
}
.mood.positive { background: var(--positive-bg); color: var(--positive); }
.mood.worried { background: var(--worried-bg); color: var(--worried); }
.mood.rival { background: var(--rival-bg); color: var(--rival); }

.insight {
  position: absolute;
  right: -8px;
  bottom: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--orange);
  color: var(--ink);
  border-radius: 14px;
  padding: 14px 18px;
  box-shadow: 0 14px 30px -14px rgba(194, 65, 12, 0.7);
  transform: rotate(-2deg);
  animation: arrive 0.5s cubic-bezier(0.2, 0.7, 0.3, 1) both;
  animation-delay: 1.9s;
}
.insight span { font-size: 14px; }
.insight strong { font-size: 19px; font-weight: 700; letter-spacing: -0.01em; }

@keyframes arrive {
  from { opacity: 0; translate: 0 14px; }
  to { opacity: 1; translate: 0 0; }
}

/* Shared section heads */
.section-title { font-size: clamp(30px, 3.6vw, 46px); line-height: 1.08; max-width: 18ch; }
.section-sub { margin-top: 12px; font-size: 18px; color: var(--ink-soft); max-width: 40em; }

/* Benefits */
.benefits-inner {
  padding-top: clamp(56px, 8vw, 112px);
  padding-bottom: clamp(56px, 8vw, 112px);
  display: flex;
  flex-wrap: wrap;
  gap: 40px 64px;
}
.benefits-title { flex: 1 1 300px; font-size: clamp(30px, 3.6vw, 46px); line-height: 1.08; }
.benefit-list {
  flex: 2 1 520px;
  min-width: 0;
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 40px 48px;
}
.benefit { display: flex; flex-direction: column; gap: 10px; }
.benefit-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: #FFEDE5;
  color: var(--orange-text);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 4px;
}
.benefit h3 { font-size: 21px; }
.benefit p { font-size: 17px; color: var(--ink-soft); }

/* How it works */
.how { background: var(--tint); }
.how .wrap { padding-top: clamp(56px, 8vw, 112px); padding-bottom: clamp(56px, 8vw, 112px); }
.steps {
  list-style: none;
  margin-top: 48px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 40px;
}
.step { display: flex; flex-direction: column; gap: 10px; border-top: 2px solid var(--ink); padding-top: 20px; }
.step-n { font-size: 56px; line-height: 1; font-weight: 600; color: var(--orange); letter-spacing: -0.04em; }
.step h3 { font-size: 22px; margin-top: 6px; }
.step p { font-size: 17px; color: var(--ink-soft); max-width: 30em; }

/* Example report */
.example .wrap { padding-top: clamp(56px, 8vw, 112px); padding-bottom: clamp(56px, 8vw, 112px); }
.report {
  margin-top: 40px;
  display: flex;
  flex-wrap: wrap;
  border: 1px solid var(--line);
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 24px 48px -32px rgba(26, 29, 36, 0.4);
}
.report-main {
  flex: 1 1 420px;
  min-width: 0;
  padding: clamp(24px, 3.5vw, 44px);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.report-side {
  flex: 1 1 380px;
  min-width: 0;
  padding: clamp(24px, 3.5vw, 44px);
  background: #F7F9FC;
  display: flex;
  flex-direction: column;
  gap: 32px;
}
.report-label { font-size: 14px; font-weight: 600; color: var(--orange-text); }
.report-main h3 { font-size: clamp(26px, 2.6vw, 34px); line-height: 1.12; margin-top: -6px; }
.report-summary { font-size: 17px; color: var(--ink-soft); }
.next-step {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: #FFF4EE;
  border-radius: 12px;
  padding: 16px 18px;
}
.next-step p { font-size: 17px; font-weight: 500; }

.bars { display: flex; flex-direction: column; gap: 12px; }
.bars .report-label { margin-bottom: 4px; }
.bar-row {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr) 28px;
  align-items: center;
  gap: 12px;
  font-size: 15px;
}
.bar-track { height: 12px; border-radius: 999px; background: #E3E8EF; overflow: hidden; }
.bar { display: block; height: 100%; border-radius: 999px; background: #9AA7BA; }
.bar.top { background: var(--orange); }
.bar-n { text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }

.quote { margin: 0; display: flex; flex-direction: column; gap: 10px; }
.quote p { font-size: 19px; line-height: 1.5; font-weight: 500; letter-spacing: -0.01em; }
.quote footer { font-size: 14px; color: var(--ink-soft); }

/* Use cases */
.uses { border-top: 1px solid var(--line); }
.uses-inner {
  padding-top: clamp(48px, 6vw, 88px);
  padding-bottom: clamp(48px, 6vw, 88px);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 32px 64px;
}
.uses-inner .section-title { flex: 1 1 320px; }
.chips { flex: 1 1 420px; list-style: none; display: flex; flex-wrap: wrap; gap: 10px; }
.chips li {
  font-size: 17px;
  font-weight: 500;
  padding: 10px 18px;
  border-radius: 999px;
  background: var(--tint);
}

/* Sign-up */
.signup { background: var(--tint); }
.signup-inner {
  padding-top: clamp(56px, 8vw, 112px);
  padding-bottom: clamp(56px, 8vw, 112px);
  display: flex;
  flex-wrap: wrap;
  gap: 40px 72px;
  align-items: flex-start;
}
.signup-copy { flex: 1 1 340px; min-width: 0; display: flex; flex-direction: column; gap: 20px; }
.signup-copy h2 { font-size: clamp(34px, 4.2vw, 56px); line-height: 1.04; letter-spacing: -0.03em; }
.signup-copy p { font-size: 18px; color: var(--ink-soft); max-width: 30em; }
.points { list-style: none; display: flex; flex-direction: column; gap: 12px; font-size: 17px; }
.points li { display: flex; gap: 12px; align-items: baseline; }
.points li::before {
  content: '';
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--orange);
  flex: none;
  translate: 0 -2px;
}
.signup-form { flex: 1 1 500px; min-width: 0; }

/* Footer */
.footer { border-top: 1px solid var(--line); color: var(--ink-soft); }
.footer-inner {
  padding-top: 24px;
  padding-bottom: 24px;
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 8px 24px;
  font-size: 14px;
}

@media (max-width: 640px) {
  .nav { flex-wrap: nowrap; }
  .nav-links a:not(.btn) { display: none; }
  .board { padding-bottom: 0; }
  .reactions { margin-left: 18px; padding-left: 18px; }
  .reaction::before { left: -19px; width: 18px; }
  .insight { position: static; margin-top: 16px; transform: none; }
  .bar-row { grid-template-columns: 110px minmax(0, 1fr) 24px; font-size: 14px; }
}

@media (prefers-reduced-motion: reduce) {
  .reaction, .insight { animation: none; }
  .btn { transition: none; }
}
</style>
