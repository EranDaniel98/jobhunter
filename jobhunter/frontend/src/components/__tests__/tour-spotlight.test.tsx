import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { TourSpotlight } from '../dashboard/tour-spotlight'

describe('TourSpotlight', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('renders nothing when target element is not found', () => {
    const { container } = render(<TourSpotlight selector="nonexistent" />)
    expect(container.innerHTML).toBe('')
  })

  it('renders spotlight when target element exists', () => {
    // Create a target element in the DOM
    const target = document.createElement('div')
    target.setAttribute('data-tour', 'test-target')
    // jsdom doesn't layout, so getBoundingClientRect returns zeros
    target.getBoundingClientRect = vi.fn(() => ({
      top: 100,
      left: 200,
      width: 300,
      height: 50,
      bottom: 150,
      right: 500,
      x: 200,
      y: 100,
      toJSON: () => {},
    }))
    document.body.appendChild(target)

    const { container } = render(<TourSpotlight selector="test-target" />)
    const spotlight = container.firstChild as HTMLElement
    expect(spotlight).toBeTruthy()
    expect(spotlight.style.boxShadow).toContain('9999px')
  })

  it('applies padding to spotlight rect', () => {
    const target = document.createElement('div')
    target.setAttribute('data-tour', 'padded')
    target.getBoundingClientRect = vi.fn(() => ({
      top: 100,
      left: 200,
      width: 300,
      height: 50,
      bottom: 150,
      right: 500,
      x: 200,
      y: 100,
      toJSON: () => {},
    }))
    document.body.appendChild(target)

    const padding = 12
    const { container } = render(<TourSpotlight selector="padded" padding={padding} />)
    const spotlight = container.firstChild as HTMLElement

    // top = 100 - 12 = 88, left = 200 - 12 = 188
    // width = 300 + 24 = 324, height = 50 + 24 = 74
    expect(spotlight.style.top).toBe('88px')
    expect(spotlight.style.left).toBe('188px')
    expect(spotlight.style.width).toBe('324px')
    expect(spotlight.style.height).toBe('74px')
  })

  it('has rounded-2xl class for soft cutout', () => {
    const target = document.createElement('div')
    target.setAttribute('data-tour', 'rounded')
    target.getBoundingClientRect = vi.fn(() => ({
      top: 0, left: 0, width: 100, height: 100, bottom: 100, right: 100, x: 0, y: 0, toJSON: () => {},
    }))
    document.body.appendChild(target)

    const { container } = render(<TourSpotlight selector="rounded" />)
    expect(container.firstChild).toHaveClass('rounded-2xl')
  })

  it('is pointer-events-none so clicks pass through', () => {
    const target = document.createElement('div')
    target.setAttribute('data-tour', 'clickthrough')
    target.getBoundingClientRect = vi.fn(() => ({
      top: 0, left: 0, width: 100, height: 100, bottom: 100, right: 100, x: 0, y: 0, toJSON: () => {},
    }))
    document.body.appendChild(target)

    const { container } = render(<TourSpotlight selector="clickthrough" />)
    expect(container.firstChild).toHaveClass('pointer-events-none')
  })

  it('calls scrollIntoView on the target element', () => {
    const target = document.createElement('div')
    target.setAttribute('data-tour', 'scroll')
    target.getBoundingClientRect = vi.fn(() => ({
      top: 0, left: 0, width: 100, height: 100, bottom: 100, right: 100, x: 0, y: 0, toJSON: () => {},
    }))
    target.scrollIntoView = vi.fn()
    document.body.appendChild(target)

    render(<TourSpotlight selector="scroll" />)
    expect(target.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' })
  })
})
