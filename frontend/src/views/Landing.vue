<template>
  <div class="landing">
    <header class="nav-bar">
      <nav class="wrap nav" aria-label="Main">
        <a href="#top" class="brand" @click.prevent="jump('top')">
          <span class="brand-mark" aria-hidden="true"></span>SIMSEND
        </a>
        <div class="nav-links">
          <a href="#story" @click.prevent="jump('story')">How it works</a>
          <a href="#sample" @click.prevent="jump('sample')">Sample run</a>
          <a href="https://github.com/TheRedSnail/SimSend" target="_blank" rel="noopener">GitHub ↗</a>
          <a href="#signup" class="nav-cta" @click.prevent="jump('signup')">Get early access</a>
        </div>
      </nav>
    </header>

    <main>
      <!-- Hero -->
      <section id="top" class="hero">
        <div class="wrap hero-inner">
          <div class="hero-copy">
            <div class="tag-row">
              <span class="tag">Audience simulation</span>
              <span class="tag-note">open source</span>
            </div>
            <h1>Rehearse your campaign <span class="accent">before it goes live.</span></h1>
            <p class="lede">
              Upload your brief and the market research you already have. SimSend builds the customers,
              competitors and press around your brand as AI personas, lets them react on two simulated
              social platforms, and reports what they actually did.
            </p>
            <div class="ctas">
              <a href="#signup" class="btn btn-primary" @click.prevent="jump('signup')">Get early access <span aria-hidden="true">→</span></a>
              <a href="#story" class="btn btn-ghost" @click.prevent="jump('story')">See how it works <span aria-hidden="true">↓</span></a>
            </div>
            <p class="hero-note">Works from PDF, Markdown or plain text</p>
          </div>

          <div id="sample" class="run-window" aria-label="Sample simulation run">
            <div class="run-head">
              <span class="run-title"><i class="live-dot" aria-hidden="true"></i>Sample run · velora-price-change</span>
              <span>simulated hour 31 / 168</span>
            </div>
            <div class="run-progress"><span></span></div>
            <div class="run-tabs">
              <span class="run-tab active">Feed (Twitter-style)</span>
              <span class="run-tab">Forum (Reddit-style)</span>
            </div>
            <article v-for="p in HERO_POSTS" :key="p.who" class="run-post">
              <span class="run-avatar" :class="p.tone" aria-hidden="true">{{ p.initials }}</span>
              <div class="run-body">
                <div class="run-post-head">
                  <b>{{ p.who }}</b><span class="run-role">{{ p.role }}</span><span class="run-action">{{ p.action }}</span>
                </div>
                <p>{{ p.text }}</p>
                <span class="run-stats">{{ p.stats }}</span>
              </div>
            </article>
            <div class="run-activity">
              <span><b>Student paper</b> searched “Velora price 2025”</span>
              <span><b>Stadsrijder</b> liked Pedaalpas's post</span>
            </div>
          </div>
        </div>
      </section>

      <ScrollStory />

      <!-- Sign-up -->
      <section id="signup" class="signup">
        <div class="wrap signup-inner">
          <div class="signup-copy">
            <span class="eyebrow">Early access</span>
            <h2>Rehearse your next campaign with us.</h2>
            <p>
              SimSend is in early access. Leave your details and we'll set you up with a workspace and the
              sample brief, so your first run takes minutes.
            </p>
            <ul class="points">
              <li>Runs on the documents you already have</li>
              <li>Every report claim traceable to the action log</li>
              <li>Open source, self-hostable</li>
            </ul>
          </div>
          <SignupForm class="signup-form" />
        </div>
      </section>
    </main>

    <footer class="footer">
      <div class="wrap footer-inner">
        <span>SimSend · fork of MiroFish · AGPL-3.0</span>
        <span>Sample run content is illustrative</span>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import ScrollStory from '../components/landing/ScrollStory.vue'
import SignupForm from '../components/landing/SignupForm.vue'

const HERO_POSTS = [
  {
    who: 'Lotte M.',
    role: 'Student · Utrecht',
    initials: 'LM',
    tone: 'light',
    action: 'Post',
    text: 'ok Velora gave 5 weeks notice AND explained why. and students keep the old price until 2027. last time it was 7 days and no reason. this is better',
    stats: '14 likes · 3 reposts'
  },
  {
    who: 'Pedaalpas',
    role: 'Competitor',
    initials: 'PP',
    tone: 'orange',
    action: 'Post',
    text: "Hearing some bikes are getting more expensive in December. Ours aren't. Just saying.",
    stats: '41 likes · 12 reposts'
  },
  {
    who: 'Arjun R.',
    role: 'International student · Groningen',
    initials: 'AR',
    tone: 'blue',
    action: 'Reply',
    text: 'Was the email only in Dutch? I almost deleted it. Does the price lock apply to me if I joined in September?',
    stats: '9 likes'
  }
]

const jump = (id) => {
  const el = document.getElementById(id)
  if (!el) return
  const reduce = typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
  if (window.location.hash !== `#${id}`) history.replaceState(history.state, '', `#${id}`)
}

let previousTitle = ''
onMounted(() => {
  previousTitle = document.title
  document.title = 'SimSend · Rehearse your campaign before it goes live'
  const id = window.location.hash.slice(1)
  if (id) requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView())
})
onBeforeUnmount(() => {
  document.title = previousTitle
})
</script>

<style scoped>
.landing {
  --ink: #0A0A0A;
  --ink-2: #141414;
  --paper: #F5F5F5;
  --white: #FFFFFF;
  --orange: #FF4500;
  --blue: #3B82F6;
  --mono: 'JetBrains Mono', monospace;
  --sans: 'Space Grotesk', system-ui, sans-serif;
  font-family: var(--sans);
  color: var(--ink);
  background: var(--ink);
  min-width: 0;
}

.wrap {
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
  padding-left: clamp(16px, 4vw, 40px);
  padding-right: clamp(16px, 4vw, 40px);
}

a { color: inherit; }
a:focus-visible, .btn:focus-visible { outline: 3px solid var(--orange); outline-offset: 2px; }

/* Nav */
.nav-bar { background: var(--ink); color: var(--white); border-bottom: 1px solid #222222; }
.nav {
  min-height: 64px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px 32px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  font-family: var(--mono);
  font-weight: 700;
  font-size: 18px;
  letter-spacing: 1px;
}
.brand-mark { width: 14px; height: 14px; background: var(--orange); }
.nav-links {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 28px;
  font-family: var(--mono);
  font-size: 14px;
}
.nav-links a { color: #D4D4D4; text-decoration: none; padding: 12px 0; }
.nav-links a:hover { color: var(--white); }
.nav-links .nav-cta { background: var(--orange); color: var(--ink); font-weight: 700; padding: 12px 18px; }
.nav-links .nav-cta:hover { color: var(--ink); background: #FF6A33; }

/* Hero */
.hero { background: var(--ink); color: var(--white); }
.hero-inner {
  padding-top: clamp(48px, 7vw, 96px);
  padding-bottom: clamp(56px, 8vw, 112px);
  display: flex;
  flex-wrap: wrap;
  gap: 56px;
  align-items: center;
}
.hero-copy { flex: 1 1 440px; min-width: 0; display: flex; flex-direction: column; gap: 28px; }
.tag-row { display: flex; align-items: center; gap: 12px; font-family: var(--mono); font-size: 13px; letter-spacing: 1px; }
.tag { background: var(--orange); color: var(--ink); font-weight: 700; padding: 4px 10px; text-transform: uppercase; }
.tag-note { color: #A3A3A3; }
h1 {
  font-size: clamp(44px, 5.6vw, 80px);
  line-height: 1.02;
  font-weight: 600;
  letter-spacing: -0.03em;
}
.accent { color: var(--orange); }
.lede { font-size: 19px; line-height: 1.6; color: #C7C7C7; max-width: 560px; }
.ctas { display: flex; flex-wrap: wrap; gap: 12px; }
.btn {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  text-decoration: none;
  font-size: 17px;
  padding: 16px 24px;
  transition: background-color 0.2s, border-color 0.2s;
}
.btn-primary { background: var(--orange); color: var(--ink); font-weight: 700; }
.btn-primary:hover { background: #FF6A33; }
.btn-ghost { border: 1px solid #555555; color: var(--white); font-weight: 500; }
.btn-ghost:hover { border-color: var(--white); }
.hero-note { font-family: var(--mono); font-size: 13px; color: #8A8A8A; }

/* Run window */
.run-window {
  flex: 1 1 520px;
  min-width: 0;
  background: var(--ink-2);
  border: 1px solid #2A2A2A;
  box-shadow: 16px 16px 0 var(--orange);
}
.run-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 18px;
  border-bottom: 1px solid #2A2A2A;
  font-family: var(--mono);
  font-size: 12px;
  color: #A3A3A3;
}
.run-title { display: flex; align-items: center; gap: 8px; color: var(--white); text-transform: uppercase; }
.live-dot { width: 8px; height: 8px; background: var(--orange); animation: blink 1.4s ease-in-out infinite; }
.run-progress { height: 3px; background: #262626; }
.run-progress span { display: block; width: 18%; height: 3px; background: var(--orange); }
.run-tabs { display: flex; flex-wrap: wrap; border-bottom: 1px solid #2A2A2A; font-family: var(--mono); font-size: 12px; }
.run-tab { padding: 12px 18px; color: #8A8A8A; }
.run-tab.active { color: var(--white); border-bottom: 2px solid var(--orange); }
.run-post { display: flex; gap: 14px; padding: 18px; border-bottom: 1px solid #222222; }
.run-avatar {
  width: 40px;
  height: 40px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--mono);
  font-weight: 700;
  font-size: 13px;
  color: var(--ink);
}
.run-avatar.light { background: var(--paper); }
.run-avatar.orange { background: var(--orange); }
.run-avatar.blue { background: var(--blue); }
.run-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.run-post-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 14px; }
.run-role { color: #A3A3A3; font-family: var(--mono); font-size: 11px; text-transform: uppercase; }
.run-action {
  margin-left: auto;
  font-family: var(--mono);
  font-size: 11px;
  text-transform: uppercase;
  color: var(--ink);
  background: #E5E5E5;
  padding: 2px 6px;
}
.run-body p { color: #E5E5E5; font-size: 15px; line-height: 1.5; }
.run-stats { font-family: var(--mono); font-size: 12px; color: #8A8A8A; }
.run-activity {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  padding: 14px 18px;
  font-family: var(--mono);
  font-size: 12px;
  color: #A3A3A3;
}
.run-activity b { color: var(--white); font-weight: 500; }

/* Sign-up */
.signup { background: var(--ink); color: var(--white); border-top: 1px solid #222222; }
.signup-inner {
  padding-top: clamp(56px, 8vw, 112px);
  padding-bottom: clamp(56px, 8vw, 112px);
  display: flex;
  flex-wrap: wrap;
  gap: 48px 72px;
  align-items: flex-start;
}
.signup-copy { flex: 1 1 360px; min-width: 0; display: flex; flex-direction: column; gap: 22px; }
.eyebrow { font-family: var(--mono); font-size: 13px; letter-spacing: 1px; color: var(--orange); text-transform: uppercase; }
.signup-copy h2 { font-size: clamp(36px, 4.4vw, 60px); line-height: 1.02; font-weight: 600; letter-spacing: -0.03em; }
.signup-copy p { font-size: 18px; line-height: 1.6; color: #C7C7C7; max-width: 480px; }
.points { list-style: none; display: flex; flex-direction: column; gap: 12px; font-size: 16px; color: #E5E5E5; }
.points li { display: flex; gap: 12px; align-items: center; }
.points li::before { content: ''; width: 10px; height: 10px; background: var(--orange); flex: none; }
.signup-form { flex: 1 1 520px; min-width: 0; }

/* Footer */
.footer { background: var(--ink); color: #8A8A8A; border-top: 1px solid #222222; }
.footer-inner {
  padding-top: 20px;
  padding-bottom: 20px;
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 12px;
  font-family: var(--mono);
  font-size: 12px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.25; }
}

@media (prefers-reduced-motion: reduce) {
  .live-dot { animation: none; }
  .btn { transition: none; }
}
</style>
