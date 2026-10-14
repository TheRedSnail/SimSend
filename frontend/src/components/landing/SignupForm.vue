<template>
  <div class="signup-card">
    <div v-if="done" class="thanks" role="status">
      <span class="thanks-mark" aria-hidden="true"></span>
      <h3>Thanks, {{ firstName }}.</h3>
      <p>You're on the list. We'll get in touch at <b>{{ submittedEmail }}</b> when your workspace is ready.</p>
    </div>

    <form v-else novalidate @submit.prevent="submit">
      <div class="grid">
        <div class="field">
          <label for="signup-name">Full name</label>
          <input
            id="signup-name"
            v-model="form.name"
            type="text"
            autocomplete="name"
            maxlength="120"
            :aria-invalid="!!errors.name"
            :aria-describedby="errors.name ? 'signup-name-error' : undefined"
          >
          <span v-if="errors.name" id="signup-name-error" class="error">{{ errors.name }}</span>
        </div>
        <div class="field">
          <label for="signup-email">Work email</label>
          <input
            id="signup-email"
            v-model="form.email"
            type="email"
            autocomplete="email"
            maxlength="254"
            :aria-invalid="!!errors.email"
            :aria-describedby="errors.email ? 'signup-email-error' : undefined"
          >
          <span v-if="errors.email" id="signup-email-error" class="error">{{ errors.email }}</span>
        </div>
        <div class="field">
          <label for="signup-company">Company <span class="optional">Optional</span></label>
          <input
            id="signup-company"
            v-model="form.company"
            type="text"
            autocomplete="organization"
            maxlength="160"
          >
        </div>
        <div class="field">
          <label for="signup-role">Role <span class="optional">Optional</span></label>
          <select id="signup-role" v-model="form.role">
            <option value="">Choose one</option>
            <option v-for="r in ROLES" :key="r.value" :value="r.value">{{ r.label }}</option>
          </select>
        </div>
      </div>

      <div class="field">
        <label for="signup-use-case">What would you simulate first? <span class="optional">Optional</span></label>
        <textarea
          id="signup-use-case"
          v-model="form.use_case"
          rows="3"
          maxlength="1000"
          placeholder="E.g. how our students react to a price change"
        ></textarea>
      </div>

      <!-- Honeypot: hidden from people and screen readers, filled in by bots. -->
      <div class="hp" aria-hidden="true">
        <label for="signup-website">Website</label>
        <input id="signup-website" v-model="form.website" type="text" tabindex="-1" autocomplete="off">
      </div>

      <label class="check">
        <input v-model="form.updates" type="checkbox">
        Send me product updates
      </label>

      <p v-if="submitError" class="submit-error" role="alert">{{ submitError }}</p>

      <button type="submit" class="submit" :disabled="submitting">
        <span>{{ submitting ? 'Sending…' : 'Request access' }}</span>
        <span aria-hidden="true">→</span>
      </button>
      <p class="fineprint">We only use this to contact you about SimSend.</p>
    </form>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { submitSignup } from '../../api/signup'

const ROLES = [
  { value: 'marketing', label: 'Marketing' },
  { value: 'brand', label: 'Brand or communications' },
  { value: 'agency', label: 'Agency' },
  { value: 'research', label: 'Research and insights' },
  { value: 'founder', label: 'Founder' },
  { value: 'other', label: 'Other' }
]

const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$/

const form = reactive({
  name: '',
  email: '',
  company: '',
  role: '',
  use_case: '',
  updates: false,
  website: ''
})
const errors = reactive({ name: '', email: '' })
const submitting = ref(false)
const submitError = ref('')
const done = ref(false)
const submittedName = ref('')
const submittedEmail = ref('')

const firstName = computed(() => submittedName.value.split(' ')[0] || 'there')

const validate = () => {
  errors.name = form.name.trim() ? '' : 'Enter your name.'
  const email = form.email.trim()
  if (!email) errors.email = 'Enter your work email.'
  else if (!EMAIL_RE.test(email)) errors.email = 'Enter a valid email address, like name@company.com.'
  else errors.email = ''
  return !errors.name && !errors.email
}

const submit = async () => {
  submitError.value = ''
  if (!validate()) {
    document.getElementById(errors.name ? 'signup-name' : 'signup-email')?.focus()
    return
  }
  submitting.value = true
  try {
    await submitSignup({
      name: form.name,
      email: form.email.trim(),
      company: form.company,
      role: form.role,
      use_case: form.use_case,
      updates: form.updates,
      website: form.website
    })
    submittedName.value = form.name.trim()
    submittedEmail.value = form.email.trim()
    done.value = true
  } catch (err) {
    submitError.value = err?.message && err.message !== 'Request failed'
      ? err.message
      : 'Something went wrong. Please try again.'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.signup-card {
  background: var(--white);
  color: var(--ink);
  padding: clamp(20px, 3vw, 36px);
  box-shadow: 12px 12px 0 var(--orange);
}

form { display: flex; flex-direction: column; gap: 18px; }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}
.field { display: flex; flex-direction: column; gap: 6px; }
label { font-size: 14px; font-weight: 600; }
.optional { font-weight: 400; color: #525252; margin-left: 4px; }

input[type="text"],
input[type="email"],
select,
textarea {
  min-height: 46px;
  border: 1px solid #737373;
  border-radius: 0;
  padding: 0 12px;
  font-family: var(--sans);
  font-size: 16px;
  background: var(--white);
  color: var(--ink);
}
textarea { padding: 12px; resize: vertical; }
input:focus-visible, select:focus-visible, textarea:focus-visible, .submit:focus-visible {
  outline: 3px solid var(--orange);
  outline-offset: 1px;
}
input[aria-invalid="true"] { border-color: #B42318; }
.error { font-size: 13px; color: #B42318; }

.hp {
  position: absolute;
  left: -10000px;
  width: 1px;
  height: 1px;
  overflow: hidden;
}

.check {
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 15px;
  font-weight: 400;
  min-height: 44px;
  cursor: pointer;
}
.check input { width: 20px; height: 20px; accent-color: var(--ink); }

.submit-error {
  font-size: 14px;
  color: #B42318;
  border: 1px solid #B42318;
  padding: 10px 12px;
}

.submit {
  min-height: 56px;
  background: var(--ink);
  color: var(--white);
  border: none;
  font-family: var(--mono);
  font-weight: 700;
  font-size: 16px;
  letter-spacing: 1px;
  text-transform: uppercase;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  cursor: pointer;
  transition: background-color 0.2s;
}
.submit:hover:not(:disabled) { background: #262626; }
.submit:disabled { opacity: 0.6; cursor: progress; }
.fineprint { font-size: 13px; color: #525252; }

.thanks { display: flex; flex-direction: column; gap: 14px; padding: 24px 0; }
.thanks-mark { width: 16px; height: 16px; background: var(--orange); }
.thanks h3 { font-size: 32px; font-weight: 600; letter-spacing: -0.02em; }
.thanks p { font-size: 17px; line-height: 1.6; color: #404040; }
</style>
