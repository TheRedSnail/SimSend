import { describe, expect, it } from 'vitest'
import { renderMarkdown } from './markdown'

describe('renderMarkdown', () => {
  it('returns an empty string for empty input', () => {
    expect(renderMarkdown('')).toBe('')
    expect(renderMarkdown(null)).toBe('')
  })

  it('escapes raw HTML tags so they cannot execute', () => {
    const html = renderMarkdown('<img src=x onerror="alert(1)">')
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;img')
  })

  it('escapes script tags', () => {
    const html = renderMarkdown('hello <script>alert(1)</script>')
    expect(html).not.toMatch(/<script/i)
  })

  it('escapes quotes so nothing can break out of an attribute', () => {
    const html = renderMarkdown(`- item" onmouseover="alert(1)`)
    expect(html).not.toContain('" onmouseover="')
    expect(html).toContain('&quot;')
    expect(renderMarkdown("it's")).toContain('&#39;')
  })

  it('escapes ampersands before other entities', () => {
    expect(renderMarkdown('&lt;b&gt;')).toContain('&amp;lt;b&amp;gt;')
  })

  it('does not let markdown markers smuggle markup into code spans', () => {
    const html = renderMarkdown('`<b>bold</b>`')
    expect(html).toContain('<code class="inline-code">&lt;b>bold&lt;/b></code>')
  })

  it('still renders basic markdown', () => {
    const html = renderMarkdown('# Title\n\n**bold** and *em*\n\n> quote\n\n- a\n- b')
    expect(html).toContain('<h2 class="md-h2">Title</h2>')
    expect(html).toContain('<strong>bold</strong>')
    expect(html).toContain('<em>em</em>')
    expect(html).toContain('<blockquote class="md-quote">quote</blockquote>')
    expect(html).toContain('<ul class="md-ul">')
  })
})
