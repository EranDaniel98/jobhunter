import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TourTooltip } from '../dashboard/tour-tooltip'

const defaultProps = {
  title: 'Test Title',
  description: 'Test description text',
  currentStep: 0,
  totalSteps: 10,
  onNext: vi.fn(),
  onBack: vi.fn(),
  onSkip: vi.fn(),
  isLast: false,
  isFirst: true,
}

function renderTooltip(overrides: Partial<typeof defaultProps> = {}) {
  const props = { ...defaultProps, ...overrides }
  // Reset mocks for each render
  props.onNext = overrides.onNext ?? vi.fn()
  props.onBack = overrides.onBack ?? vi.fn()
  props.onSkip = overrides.onSkip ?? vi.fn()
  return { ...render(<TourTooltip {...props} />), props }
}

describe('TourTooltip', () => {
  it('renders title and description', () => {
    renderTooltip()
    expect(screen.getByText('Test Title')).toBeInTheDocument()
    expect(screen.getByText('Test description text')).toBeInTheDocument()
  })

  it('shows step counter in "N of M" format', () => {
    renderTooltip({ currentStep: 4, totalSteps: 15 })
    expect(screen.getByText('5 of 15')).toBeInTheDocument()
  })

  it('shows "Next" button when not on last step', () => {
    renderTooltip({ isLast: false })
    expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /finish/i })).not.toBeInTheDocument()
  })

  it('shows "Finish" button on last step', () => {
    renderTooltip({ isLast: true })
    expect(screen.getByRole('button', { name: /finish/i })).toBeInTheDocument()
  })

  it('hides Back button on first step', () => {
    renderTooltip({ isFirst: true })
    expect(screen.queryByRole('button', { name: /back/i })).not.toBeInTheDocument()
  })

  it('shows Back button on non-first steps', () => {
    renderTooltip({ isFirst: false, currentStep: 3 })
    expect(screen.getByRole('button', { name: /back/i })).toBeInTheDocument()
  })

  it('calls onNext when Next is clicked', async () => {
    const user = userEvent.setup()
    const { props } = renderTooltip()
    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(props.onNext).toHaveBeenCalledOnce()
  })

  it('calls onBack when Back is clicked', async () => {
    const user = userEvent.setup()
    const { props } = renderTooltip({ isFirst: false, currentStep: 2 })
    await user.click(screen.getByRole('button', { name: /back/i }))
    expect(props.onBack).toHaveBeenCalledOnce()
  })

  it('calls onSkip when Skip tour is clicked', async () => {
    const user = userEvent.setup()
    const { props } = renderTooltip()
    await user.click(screen.getByRole('button', { name: /skip tour/i }))
    expect(props.onSkip).toHaveBeenCalledOnce()
  })

  it('calls onSkip when X close button is clicked', async () => {
    const user = userEvent.setup()
    const { props } = renderTooltip()
    // X button is the icon button (first ghost button that is not "Skip tour")
    const buttons = screen.getAllByRole('button')
    // The X button is the small icon button in the header
    const xButton = buttons.find(
      (b) => b.querySelector('svg') && !b.textContent?.includes('Skip')
        && !b.textContent?.includes('Next') && !b.textContent?.includes('Back')
    )
    expect(xButton).toBeDefined()
    await user.click(xButton!)
    expect(props.onSkip).toHaveBeenCalledOnce()
  })

  it('renders progress bar with correct width', () => {
    const { container } = renderTooltip({ currentStep: 4, totalSteps: 10 })
    // Progress should be 50% ((4+1)/10 * 100)
    const progressBar = container.querySelector('.bg-primary')
    expect(progressBar).toHaveStyle({ width: '50%' })
  })

  it('renders progress bar at 100% on last step', () => {
    const { container } = renderTooltip({ currentStep: 9, totalSteps: 10, isLast: true })
    const progressBar = container.querySelector('.bg-primary')
    expect(progressBar).toHaveStyle({ width: '100%' })
  })

  it('always shows Skip tour button', () => {
    renderTooltip({ isFirst: true })
    expect(screen.getByRole('button', { name: /skip tour/i })).toBeInTheDocument()
  })
})
