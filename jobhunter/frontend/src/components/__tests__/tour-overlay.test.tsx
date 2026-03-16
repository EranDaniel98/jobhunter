import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TourOverlay } from '../dashboard/tour-overlay'

// --- Mocks ---

const mockPush = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}))

const mockCompleteTour = vi.fn(() => Promise.resolve())
let mockIsTourCompleted = false

vi.mock('@/providers/auth-provider', () => ({
  useAuth: () => ({
    isTourCompleted: mockIsTourCompleted,
    completeTour: mockCompleteTour,
  }),
}))

// Mock tour steps with a small set for easier testing
vi.mock('@/lib/tour-steps', () => ({
  TOUR_STEPS: [
    { selector: 'nav-core', title: 'Step 1', description: 'Desc 1', route: '/dashboard' },
    { selector: 'next-actions', title: 'Step 2', description: 'Desc 2', route: '/dashboard' },
    { selector: 'page-header', title: 'Step 3', description: 'Desc 3', route: '/resume' },
    { selector: 'page-header', title: 'Step 4', description: 'Desc 4', route: '/companies' },
  ],
}))

function createTourTarget(selector: string) {
  const el = document.createElement('div')
  el.setAttribute('data-tour', selector)
  el.getBoundingClientRect = vi.fn(() => ({
    top: 100, left: 100, width: 200, height: 50,
    bottom: 150, right: 300, x: 100, y: 100, toJSON: () => {},
  }))
  el.scrollIntoView = vi.fn()
  document.body.appendChild(el)
  return el
}

describe('TourOverlay', () => {
  beforeEach(() => {
    mockIsTourCompleted = false
    mockPush.mockClear()
    mockCompleteTour.mockClear()
    document.body.innerHTML = ''
    document.body.style.overflow = ''
    document.body.style.paddingRight = ''
    // Set desktop viewport
    Object.defineProperty(window, 'innerWidth', { value: 1200, writable: true })
    Object.defineProperty(document.documentElement, 'clientWidth', { value: 1185, writable: true })
    // Set pathname
    Object.defineProperty(window, 'location', {
      value: { pathname: '/dashboard' },
      writable: true,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // --- Rendering ---

  it('renders when tour is not completed', () => {
    createTourTarget('nav-core')
    render(<TourOverlay />)
    expect(screen.getByText('Step 1')).toBeInTheDocument()
    expect(screen.getByText('Desc 1')).toBeInTheDocument()
  })

  it('renders nothing when tour is completed', () => {
    mockIsTourCompleted = true
    const { container } = render(<TourOverlay />)
    expect(container.innerHTML).toBe('')
  })

  it('renders click blocker overlay', () => {
    createTourTarget('nav-core')
    const { container } = render(<TourOverlay />)
    const blocker = container.querySelector('.fixed.inset-0.z-\\[59\\]')
    expect(blocker).toBeInTheDocument()
  })

  // --- Scroll lock ---

  it('locks body scroll when tour is active', () => {
    createTourTarget('nav-core')
    render(<TourOverlay />)
    expect(document.body.style.overflow).toBe('hidden')
  })

  it('compensates for scrollbar width', () => {
    createTourTarget('nav-core')
    render(<TourOverlay />)
    // innerWidth(1200) - clientWidth(1185) = 15px
    expect(document.body.style.paddingRight).toBe('15px')
  })

  it('restores scroll on unmount', () => {
    createTourTarget('nav-core')
    const { unmount } = render(<TourOverlay />)
    expect(document.body.style.overflow).toBe('hidden')
    unmount()
    expect(document.body.style.overflow).toBe('')
    expect(document.body.style.paddingRight).toBe('')
  })

  // --- Navigation ---

  it('advances to next step on Next click', async () => {
    const user = userEvent.setup()
    createTourTarget('nav-core')
    createTourTarget('next-actions')
    render(<TourOverlay />)

    expect(screen.getByText('Step 1')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText('Step 2')).toBeInTheDocument()
  })

  it('hides Back button on first step', () => {
    createTourTarget('nav-core')
    render(<TourOverlay />)
    expect(screen.queryByRole('button', { name: /back/i })).not.toBeInTheDocument()
  })

  it('shows Back button on second step', async () => {
    const user = userEvent.setup()
    createTourTarget('nav-core')
    createTourTarget('next-actions')
    render(<TourOverlay />)

    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByRole('button', { name: /back/i })).toBeInTheDocument()
  })

  it('goes back to previous step on Back click', async () => {
    const user = userEvent.setup()
    createTourTarget('nav-core')
    createTourTarget('next-actions')
    render(<TourOverlay />)

    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText('Step 2')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /back/i }))
    expect(screen.getByText('Step 1')).toBeInTheDocument()
  })

  it('calls router.push when navigating to a different route', async () => {
    const user = userEvent.setup()
    createTourTarget('nav-core')
    createTourTarget('next-actions')
    createTourTarget('page-header')
    render(<TourOverlay />)

    // Step 1 -> Step 2 (same route, no push)
    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(mockPush).not.toHaveBeenCalled()

    // Step 2 -> Step 3 (route: /resume, different from /dashboard)
    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(mockPush).toHaveBeenCalledWith('/resume')
  })

  // --- Skip / Finish ---

  it('calls completeTour and navigates to dashboard on skip', async () => {
    const user = userEvent.setup()
    createTourTarget('nav-core')
    render(<TourOverlay />)

    await user.click(screen.getByRole('button', { name: /skip tour/i }))
    expect(mockCompleteTour).toHaveBeenCalledOnce()
    expect(mockPush).toHaveBeenCalledWith('/dashboard')
  })

  it('renders nothing after skip', async () => {
    const user = userEvent.setup()
    createTourTarget('nav-core')
    const { container } = render(<TourOverlay />)

    await user.click(screen.getByRole('button', { name: /skip tour/i }))
    expect(container.innerHTML).toBe('')
  })

  it('restores body scroll after skip', async () => {
    const user = userEvent.setup()
    createTourTarget('nav-core')
    render(<TourOverlay />)
    expect(document.body.style.overflow).toBe('hidden')

    await user.click(screen.getByRole('button', { name: /skip tour/i }))
    expect(document.body.style.overflow).toBe('')
  })

  // --- Keyboard navigation ---

  it('advances on Enter key', async () => {
    const user = userEvent.setup()
    createTourTarget('nav-core')
    createTourTarget('next-actions')
    render(<TourOverlay />)

    expect(screen.getByText('Step 1')).toBeInTheDocument()
    await user.keyboard('{Enter}')
    expect(screen.getByText('Step 2')).toBeInTheDocument()
  })

  it('advances on ArrowRight key', async () => {
    const user = userEvent.setup()
    createTourTarget('nav-core')
    createTourTarget('next-actions')
    render(<TourOverlay />)

    await user.keyboard('{ArrowRight}')
    expect(screen.getByText('Step 2')).toBeInTheDocument()
  })

  it('goes back on ArrowLeft key', async () => {
    const user = userEvent.setup()
    createTourTarget('nav-core')
    createTourTarget('next-actions')
    render(<TourOverlay />)

    await user.keyboard('{ArrowRight}')
    expect(screen.getByText('Step 2')).toBeInTheDocument()

    await user.keyboard('{ArrowLeft}')
    expect(screen.getByText('Step 1')).toBeInTheDocument()
  })

  it('does not go back past first step on ArrowLeft', async () => {
    const user = userEvent.setup()
    createTourTarget('nav-core')
    render(<TourOverlay />)

    await user.keyboard('{ArrowLeft}')
    // Still on step 1
    expect(screen.getByText('Step 1')).toBeInTheDocument()
  })

  it('skips tour on Escape key', async () => {
    const user = userEvent.setup()
    createTourTarget('nav-core')
    render(<TourOverlay />)

    await user.keyboard('{Escape}')
    expect(mockCompleteTour).toHaveBeenCalledOnce()
    expect(mockPush).toHaveBeenCalledWith('/dashboard')
  })

  // --- Mobile behavior ---

  it('filters out nav-* steps on mobile viewport', () => {
    Object.defineProperty(window, 'innerWidth', { value: 800, writable: true })
    createTourTarget('next-actions')
    render(<TourOverlay />)

    // First visible step should be Step 2 (next-actions), since nav-core is filtered
    expect(screen.getByText('Step 2')).toBeInTheDocument()
    // Total steps shown should be 3 (nav-core filtered out)
    expect(screen.getByText('1 of 3')).toBeInTheDocument()
  })

  // --- Navigation lock ---

  it('prevents double-advance during route navigation', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    createTourTarget('nav-core')
    createTourTarget('next-actions')
    createTourTarget('page-header')
    render(<TourOverlay />)

    // Go to step 2
    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText('Step 2')).toBeInTheDocument()

    // Click next — triggers route navigation to /resume with 600ms delay
    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(mockPush).toHaveBeenCalledWith('/resume')

    // Click next again immediately — should be blocked by navigation lock
    await user.click(screen.getByRole('button', { name: /next/i }))
    // router.push should only have been called once (the /resume call)
    expect(mockPush).toHaveBeenCalledTimes(1)

    // After timeout, step should advance and lock should release
    await act(async () => {
      vi.advanceTimersByTime(600)
    })

    vi.useRealTimers()
  })

  // --- Step counter ---

  it('shows correct step counter', async () => {
    const user = userEvent.setup()
    createTourTarget('nav-core')
    createTourTarget('next-actions')
    render(<TourOverlay />)

    expect(screen.getByText('1 of 4')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText('2 of 4')).toBeInTheDocument()
  })
})
