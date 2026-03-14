import { describe, it, expect } from 'vitest'
import {
  cn,
  formatDate,
  formatDateTime,
  formatPercent,
  truncate,
  fitScoreColor,
  fitScoreBarColor,
} from '../utils'

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('px-2', 'py-1')).toBe('px-2 py-1')
  })

  it('resolves Tailwind conflicts (last wins)', () => {
    const result = cn('px-2', 'px-4')
    expect(result).toBe('px-4')
  })

  it('handles conditional classes', () => {
    expect(cn('base', false && 'hidden', 'end')).toBe('base end')
  })

  it('returns empty string for no inputs', () => {
    expect(cn()).toBe('')
  })
})

describe('formatDate', () => {
  it('formats a valid date string', () => {
    // Use a fixed UTC date to avoid timezone issues
    const result = formatDate('2026-01-15T00:00:00Z')
    expect(result).toContain('Jan')
    expect(result).toContain('2026')
    expect(result).toContain('15')
  })

  it('returns em-dash for null', () => {
    expect(formatDate(null)).toBe('-')
  })

  it('returns em-dash for empty string', () => {
    expect(formatDate('')).toBe('-')
  })
})

describe('formatDateTime', () => {
  it('formats a valid datetime string', () => {
    const result = formatDateTime('2026-03-08T14:30:00Z')
    expect(result).toContain('Mar')
    expect(result).toContain('8')
  })

  it('returns em-dash for null', () => {
    expect(formatDateTime(null)).toBe('-')
  })
})

describe('formatPercent', () => {
  it('formats 0.85 as 85.0%', () => {
    expect(formatPercent(0.85)).toBe('85.0%')
  })

  it('formats 0 as 0.0%', () => {
    expect(formatPercent(0)).toBe('0.0%')
  })

  it('formats 1 as 100.0%', () => {
    expect(formatPercent(1)).toBe('100.0%')
  })

  it('rounds to one decimal', () => {
    expect(formatPercent(0.3333)).toBe('33.3%')
  })
})

describe('truncate', () => {
  it('returns string unchanged if within limit', () => {
    expect(truncate('hello', 10)).toBe('hello')
  })

  it('truncates and adds ellipsis when exceeding limit', () => {
    expect(truncate('hello world', 5)).toBe('hello…')
  })

  it('returns exact string if length equals limit', () => {
    expect(truncate('hello', 5)).toBe('hello')
  })
})

describe('fitScoreColor', () => {
  it('returns muted for null', () => {
    expect(fitScoreColor(null)).toBe('text-muted-foreground')
  })

  it('returns destructive for low scores', () => {
    expect(fitScoreColor(0.2)).toBe('text-destructive')
  })

  it('returns chart-3 for medium scores', () => {
    expect(fitScoreColor(0.5)).toBe('text-chart-3')
  })

  it('returns primary for high scores', () => {
    expect(fitScoreColor(0.8)).toBe('text-primary')
  })

  it('treats 0.4 as medium (not low)', () => {
    expect(fitScoreColor(0.4)).toBe('text-chart-3')
  })

  it('treats 0.7 as high (not medium)', () => {
    expect(fitScoreColor(0.7)).toBe('text-primary')
  })
})

describe('fitScoreBarColor', () => {
  it('returns muted indicator for null', () => {
    expect(fitScoreBarColor(null)).toContain('bg-muted-foreground')
  })

  it('returns red indicator for low scores', () => {
    expect(fitScoreBarColor(0.2)).toContain('bg-red-500')
  })

  it('returns yellow indicator for medium scores', () => {
    expect(fitScoreBarColor(0.5)).toContain('bg-yellow-400')
  })

  it('returns green indicator for high scores', () => {
    expect(fitScoreBarColor(0.8)).toContain('bg-green-500')
  })
})
