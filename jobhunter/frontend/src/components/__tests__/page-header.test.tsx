import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PageHeader } from '../shared/page-header'

describe('PageHeader', () => {
  it('renders title', () => {
    render(<PageHeader title="Test Page" />)
    expect(screen.getByText('Test Page')).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    render(<PageHeader title="Title" description="Some description" />)
    expect(screen.getByText('Some description')).toBeInTheDocument()
  })

  it('does not render description when not provided', () => {
    const { container } = render(<PageHeader title="Title" />)
    expect(container.querySelector('p')).not.toBeInTheDocument()
  })

  it('renders children when provided', () => {
    render(
      <PageHeader title="Title">
        <button>Action</button>
      </PageHeader>
    )
    expect(screen.getByRole('button', { name: 'Action' })).toBeInTheDocument()
  })

  it('sets data-tour attribute when dataTour is provided', () => {
    const { container } = render(<PageHeader title="Title" dataTour="page-header" />)
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.getAttribute('data-tour')).toBe('page-header')
  })

  it('does NOT render data-tour attribute when dataTour is omitted', () => {
    const { container } = render(<PageHeader title="Title" />)
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.hasAttribute('data-tour')).toBe(false)
  })

  it('does NOT render data-tour="undefined" when dataTour is not passed', () => {
    const { container } = render(<PageHeader title="Title" />)
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.getAttribute('data-tour')).toBeNull()
  })
})
