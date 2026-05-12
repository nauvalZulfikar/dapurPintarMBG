import { describe, it, expect } from 'vitest'

describe('vitest smoke', () => {
  it('runs', () => {
    expect(1 + 1).toBe(2)
  })

  it('jsdom env exposes document', () => {
    expect(document).toBeDefined()
    expect(document.body).toBeDefined()
  })
})
