import service from './index'

/**
 * Submit an early-access sign-up from the landing page.
 * @param {Object} data - { name, email, company?, role?, use_case?, updates?, website? }
 */
export const submitSignup = (data) => {
  return service.post('/api/signup', data, { timeout: 15000 })
}
