import { describe, it, expect } from 'vitest'
import { TOUR_STEPS } from '@/lib/tour-steps'

describe('TOUR_STEPS', () => {
  it('has at least 10 steps', () => {
    expect(TOUR_STEPS.length).toBeGreaterThanOrEqual(10)
  })

  it('starts with sidebar nav steps', () => {
    expect(TOUR_STEPS[0].selector).toBe('nav-core')
    expect(TOUR_STEPS[1].selector).toBe('nav-outreach')
    expect(TOUR_STEPS[2].selector).toBe('nav-insights')
  })

  it('has dashboard panel steps after sidebar', () => {
    const dashboardSteps = TOUR_STEPS.filter(
      (s) => s.route === '/dashboard' && !s.selector.startsWith('nav-')
    )
    expect(dashboardSteps.length).toBeGreaterThanOrEqual(2)
    expect(dashboardSteps.some((s) => s.selector === 'next-actions')).toBe(true)
    expect(dashboardSteps.some((s) => s.selector === 'stats-cards')).toBe(true)
  })

  it('includes per-page tour steps for all main pages', () => {
    const pageRoutes = TOUR_STEPS.filter((s) => s.selector === 'page-header').map((s) => s.route)
    expect(pageRoutes).toContain('/resume')
    expect(pageRoutes).toContain('/companies')
    expect(pageRoutes).toContain('/outreach')
    expect(pageRoutes).toContain('/interview-prep')
    expect(pageRoutes).toContain('/apply')
    expect(pageRoutes).toContain('/approvals')
    expect(pageRoutes).toContain('/analytics')
    expect(pageRoutes).toContain('/settings')
  })

  it('ends with a final step back on dashboard', () => {
    const lastStep = TOUR_STEPS[TOUR_STEPS.length - 1]
    expect(lastStep.route).toBe('/dashboard')
    expect(lastStep.title).toMatch(/ready/i)
  })

  it('every step has a non-empty title and description', () => {
    for (const step of TOUR_STEPS) {
      expect(step.title.length).toBeGreaterThan(0)
      expect(step.description.length).toBeGreaterThan(0)
    }
  })

  it('every step has a selector', () => {
    for (const step of TOUR_STEPS) {
      expect(step.selector.length).toBeGreaterThan(0)
    }
  })

  it('all routes are valid dashboard paths', () => {
    const validRoutes = [
      '/dashboard', '/resume', '/companies', '/outreach',
      '/interview-prep', '/apply', '/approvals', '/analytics', '/settings',
    ]
    for (const step of TOUR_STEPS) {
      if (step.route) {
        expect(validRoutes).toContain(step.route)
      }
    }
  })

  it('nav steps all point to /dashboard route', () => {
    const navSteps = TOUR_STEPS.filter((s) => s.selector.startsWith('nav-'))
    for (const step of navSteps) {
      expect(step.route).toBe('/dashboard')
    }
  })
})
