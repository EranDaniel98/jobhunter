import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { UsageCard } from '../dashboard/usage-card'

// Mock next/link
vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}))

// Mock the API call
const mockUsageData = {
  plan_tier: 'free' as const,
  quotas: {
    discovery: { used: 3, limit: 10 },
    research: { used: 1, limit: 5 },
    hunter: { used: 0, limit: 20 },
    email: { used: 7, limit: 15 },
  },
}

vi.mock('@/lib/api/candidates', () => ({
  getUsage: vi.fn(() => Promise.resolve(mockUsageData)),
}))

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    )
  }
}

describe('UsageCard', () => {
  it('renders null initially when data is not yet loaded', () => {
    const { container } = render(<UsageCard />, { wrapper: createWrapper() })
    // Before data loads, the component returns null
    expect(container.innerHTML).toBe('')
  })

  it('renders usage data after query resolves', async () => {
    render(<UsageCard />, { wrapper: createWrapper() })

    // Wait for the query to resolve and the component to render
    expect(await screen.findByText('Usage')).toBeInTheDocument()
    expect(await screen.findByText('Free Plan')).toBeInTheDocument()
  })

  it('shows quota labels', async () => {
    render(<UsageCard />, { wrapper: createWrapper() })

    expect(await screen.findByText('Company Discoveries')).toBeInTheDocument()
    expect(await screen.findByText('Company Research')).toBeInTheDocument()
    expect(await screen.findByText('Contact Lookups')).toBeInTheDocument()
    expect(await screen.findByText('Emails Sent')).toBeInTheDocument()
  })

  it('shows usage counts in "used / limit" format', async () => {
    render(<UsageCard />, { wrapper: createWrapper() })

    expect(await screen.findByText(/3 \/ 10/)).toBeInTheDocument()
    expect(await screen.findByText(/7 \/ 15/)).toBeInTheDocument()
  })

  it('shows Upgrade link for free tier', async () => {
    render(<UsageCard />, { wrapper: createWrapper() })

    const link = await screen.findByText('Upgrade')
    expect(link).toBeInTheDocument()
    expect(link.closest('a')).toHaveAttribute('href', '/plans')
  })

  it('shows period tabs', async () => {
    render(<UsageCard />, { wrapper: createWrapper() })

    expect(await screen.findByText('Daily')).toBeInTheDocument()
    expect(await screen.findByText('Weekly')).toBeInTheDocument()
    expect(await screen.findByText('Monthly')).toBeInTheDocument()
  })
})
