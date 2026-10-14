import { describe, expect, it } from 'vitest'
import {
  CHAPTER_COUNT,
  GRAPH_EDGES,
  GRAPH_NODES,
  chapterState,
  chapterTarget,
  edgeGeometry,
  revealed
} from './story'

describe('chapterState', () => {
  it('starts on the first chapter with nothing built', () => {
    const s = chapterState(0)
    expect(s.chapter).toBe(0)
    expect(s.built(0)).toBe(0)
  })

  it('ends on the last chapter fully built', () => {
    const s = chapterState(1)
    expect(s.chapter).toBe(CHAPTER_COUNT - 1)
    expect(s.built(CHAPTER_COUNT - 1)).toBe(1)
  })

  it('treats passed chapters as built and later ones as not started', () => {
    const s = chapterState(0.5)
    expect(s.chapter).toBe(2)
    expect(s.built(0)).toBe(1)
    expect(s.built(1)).toBe(1)
    expect(s.built(3)).toBe(0)
  })

  it('finishes building before the chapter ends', () => {
    // 80% through chapter 1: past the build share, so fully built.
    expect(chapterState((1 + 0.8) / CHAPTER_COUNT).built(1)).toBe(1)
  })

  it('clamps out-of-range and invalid input', () => {
    expect(chapterState(-3).chapter).toBe(0)
    expect(chapterState(7).chapter).toBe(CHAPTER_COUNT - 1)
    expect(chapterState(NaN).chapter).toBe(0)
  })
})

describe('revealed', () => {
  it('reveals items in order as the build level rises', () => {
    const shown = (built) => [0, 1, 2, 3].filter((i) => revealed(built, i, 4))
    expect(shown(0)).toEqual([])
    expect(shown(0.5)).toEqual([0, 1])
    expect(shown(1)).toEqual([0, 1, 2, 3])
  })
})

describe('chapterTarget', () => {
  it('lands inside the requested chapter', () => {
    for (let i = 0; i < CHAPTER_COUNT; i++) {
      expect(chapterState(chapterTarget(i)).chapter).toBe(i)
    }
  })
})

describe('graph data', () => {
  it('only connects nodes that exist', () => {
    const ids = new Set(GRAPH_NODES.map((n) => n.id))
    for (const [a, b] of GRAPH_EDGES) {
      expect(ids.has(a)).toBe(true)
      expect(ids.has(b)).toBe(true)
    }
  })

  it('computes edge length and angle in the 100 x 60 box', () => {
    const g = edgeGeometry({ x: 0, y: 0 }, { x: 30, y: 40 })
    expect(g.length).toBe(50)
    expect(g.top).toBe(0)
    expect(g.angle).toBeCloseTo(53.13, 2)
  })
})
