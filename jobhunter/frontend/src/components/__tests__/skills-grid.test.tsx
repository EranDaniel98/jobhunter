import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SkillsGrid } from '../resume/skills-grid'
import type { SkillResponse } from '@/lib/types'

const mockSkills: SkillResponse[] = [
  {
    id: '1',
    name: 'TypeScript',
    category: 'explicit',
    proficiency: 'advanced',
    years_experience: 5,
    evidence: 'Used TypeScript in production for 5 years',
  },
  {
    id: '2',
    name: 'Leadership',
    category: 'transferable',
    proficiency: 'intermediate',
    years_experience: 3,
    evidence: null,
  },
  {
    id: '3',
    name: 'Rust',
    category: 'adjacent',
    proficiency: null,
    years_experience: null,
    evidence: null,
  },
]

describe('SkillsGrid', () => {
  it('renders nothing when skills array is empty (edge case bug fix)', () => {
    const { container } = render(<SkillsGrid skills={[]} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders skill names', () => {
    render(<SkillsGrid skills={mockSkills} />)
    expect(screen.getByText('TypeScript')).toBeInTheDocument()
    expect(screen.getByText('Leadership')).toBeInTheDocument()
    expect(screen.getByText('Rust')).toBeInTheDocument()
  })

  it('renders the Skills card title', () => {
    render(<SkillsGrid skills={mockSkills} />)
    expect(screen.getByText('Skills')).toBeInTheDocument()
  })

  it('groups skills by category', () => {
    render(<SkillsGrid skills={mockSkills} />)
    expect(screen.getByText('explicit skills')).toBeInTheDocument()
    expect(screen.getByText('transferable skills')).toBeInTheDocument()
    expect(screen.getByText('adjacent skills')).toBeInTheDocument()
  })

  it('shows category badges', () => {
    render(<SkillsGrid skills={mockSkills} />)
    // Each skill card has a badge with the category name
    const explicitBadges = screen.getAllByText('explicit')
    expect(explicitBadges.length).toBeGreaterThanOrEqual(1)
  })

  it('shows proficiency when available', () => {
    render(<SkillsGrid skills={mockSkills} />)
    expect(screen.getByText('advanced')).toBeInTheDocument()
    expect(screen.getByText('intermediate')).toBeInTheDocument()
  })

  it('shows years of experience when available', () => {
    render(<SkillsGrid skills={mockSkills} />)
    expect(screen.getByText('5y')).toBeInTheDocument()
    expect(screen.getByText('3y')).toBeInTheDocument()
  })

  it('shows evidence icon when evidence is available', () => {
    render(<SkillsGrid skills={mockSkills} />)
    // Skills with evidence get an "Evidence-backed" icon, without get "Inferred"
    expect(screen.getByTitle('Evidence-backed')).toBeInTheDocument()
    expect(screen.getAllByTitle('Inferred')).toHaveLength(2)
  })

  it('handles a single skill', () => {
    render(<SkillsGrid skills={[mockSkills[0]]} />)
    expect(screen.getByText('TypeScript')).toBeInTheDocument()
  })

  it('handles skills with unknown category', () => {
    const unknownSkill: SkillResponse = {
      id: '99',
      name: 'Mystery Skill',
      category: 'unknown_cat',
      proficiency: null,
      years_experience: null,
      evidence: null,
    }
    render(<SkillsGrid skills={[unknownSkill]} />)
    expect(screen.getByText('Mystery Skill')).toBeInTheDocument()
    expect(screen.getByText('unknown_cat skills')).toBeInTheDocument()
  })
})
