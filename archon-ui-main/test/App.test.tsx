import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { KnowledgeBasePage } from '@/pages/KnowledgeBasePage'

describe('App Components', () => {
  it('renders KnowledgeBasePage without crashing', () => {
    render(
      <MemoryRouter>
        <ThemeProvider>
          <KnowledgeBasePage />
        </ThemeProvider>
      </MemoryRouter>
    )
    
    // Check that the page renders some content
    expect(document.body).toBeInTheDocument()
  })

  it('should display Knowledge Base heading', () => {
    render(
      <MemoryRouter>
        <ThemeProvider>
          <KnowledgeBasePage />
        </ThemeProvider>
      </MemoryRouter>
    )
    
    // Should render the Knowledge Base page content
    expect(screen.getByText('Knowledge Base')).toBeInTheDocument()
  })
}) 