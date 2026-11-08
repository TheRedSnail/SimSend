// Copy and example data for the landing page (/).
//
// The example follows an illustrative sample run of the Velora test brief.
// Swap in a recorded run's posts and numbers before relying on it.

export const CAMPAIGN = {
  brand: 'Velora',
  title: 'New prices from December',
  detail: 'Announced 5 weeks ahead. Students keep their old price until 2027.'
}

// mood: positive | worried | rival
export const REACTIONS = [
  {
    who: 'Lotte M.',
    role: 'Student, Utrecht',
    initials: 'LM',
    mood: 'positive',
    moodLabel: 'Positive',
    text: 'ok Velora gave 5 weeks notice AND explained why. last time it was 7 days and no reason. this is better'
  },
  {
    who: 'Arjun R.',
    role: 'International student, Groningen',
    initials: 'AR',
    mood: 'worried',
    moodLabel: 'Confused',
    text: 'Was the email only in Dutch? I almost deleted it. Does the price lock apply to me if I joined in September?'
  },
  {
    who: 'Pedaalpas',
    role: 'Competitor',
    initials: 'PP',
    mood: 'rival',
    moodLabel: 'Competitor move',
    text: "Hearing some bikes are getting more expensive in December. Ours aren't. Just saying."
  }
]

export const INSIGHT = {
  label: 'Most likely to switch',
  value: 'International students'
}

// icon: key into the icon paths in views/Landing.vue
export const BENEFITS = [
  {
    icon: 'alert',
    title: 'Spot backlash early',
    body: 'See which customers push back, and why, before it happens in public.'
  },
  {
    icon: 'sliders',
    title: 'Test before you spend',
    body: 'Try different messages, prices and timing without a live budget.'
  },
  {
    icon: 'quote',
    title: 'Hear it in their words',
    body: 'Read how people react, then ask any of them why.'
  },
  {
    icon: 'doc',
    title: 'Walk in with evidence',
    body: 'Get a clear report you can share with your team.'
  }
]

export const STEPS = [
  {
    title: 'Upload your brief',
    body: 'Add your campaign brief and any research you already have. PDFs and documents are fine.'
  },
  {
    title: 'Your market reacts',
    body: 'Simulated customers, competitors and press post, reply and share, hour by hour.'
  },
  {
    title: 'Read the report, ask questions',
    body: 'See what happened and who it affected, then ask follow-up questions.'
  }
]

export const EXAMPLE = {
  finding: 'International students are the most likely to switch',
  summary: '11 of their replies asked about the email language or the price lock, and none got an answer in the simulated window.',
  barsTitle: 'Posts and replies by segment',
  bars: [
    { label: "Int'l students", n: 11 },
    { label: 'Students', n: 9 },
    { label: 'Young professionals', n: 5 },
    { label: 'Competitors', n: 3 }
  ],
  quote: {
    who: 'Arjun R., international student',
    text: "Maybe. It's not the €2.45. Nobody answered whether I'm covered. If Stadsrijder is cheaper and I don't get the lock, why stay?"
  },
  nextStep: 'Answer the price-lock question for international students, in English, before a competitor does.'
}

export const USE_CASES = [
  'Price changes',
  'Product launches',
  'Campaign messaging',
  'Rebrands',
  'Crisis comms',
  'Competitor moves'
]
