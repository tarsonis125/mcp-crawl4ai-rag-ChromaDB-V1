import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MilkdownEditor } from '@/components/project-tasks/MilkdownEditor'

// Mock dependencies
vi.mock('@/services/websocketService', () => ({
  websocketService: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
    send: vi.fn(),
  }
}))

// Mock Milkdown Crepe
vi.mock('@milkdown/crepe', () => ({
  Crepe: vi.fn().mockImplementation(() => ({
    create: vi.fn().mockResolvedValue(undefined),
    destroy: vi.fn(),
    getMarkdown: vi.fn().mockReturnValue('# Test Document\n\nThis is a test.'),
  })),
  CrepeFeature: {
    HeaderMeta: 'HeaderMeta',
    LinkTooltip: 'LinkTooltip',
    ImageBlock: 'ImageBlock',
    BlockEdit: 'BlockEdit',
    ListItem: 'ListItem',
    CodeBlock: 'CodeBlock',
    Table: 'Table',
    Toolbar: 'Toolbar',
  }
}))

describe('MilkdownEditor', () => {
  const mockDocument = {
    id: 'test-doc-1',
    title: 'Test Document',
    content: {
      markdown: '# Test Document\n\nThis is a test.'
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }

  const mockOnSave = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should render editor with document title', async () => {
    render(
      <MilkdownEditor
        document={mockDocument}
        onSave={mockOnSave}
      />
    )

    expect(screen.getByText('Test Document')).toBeTruthy()
  })

  it('should show saved status initially', async () => {
    render(
      <MilkdownEditor
        document={mockDocument}
        onSave={mockOnSave}
      />
    )

    expect(screen.getByText('All changes saved')).toBeTruthy()
  })

  it('should handle markdown content', async () => {
    const docWithMarkdown = {
      ...mockDocument,
      content: {
        markdown: '# Heading\n\n- Item 1\n- Item 2'
      }
    }

    render(
      <MilkdownEditor
        document={docWithMarkdown}
        onSave={mockOnSave}
      />
    )

    expect(screen.getByText('Test Document')).toBeTruthy()
  })

  it('should handle object content without markdown', async () => {
    const docWithObjectContent = {
      ...mockDocument,
      content: {
        project_overview: {
          description: 'Test project'
        },
        goals: ['Goal 1', 'Goal 2']
      }
    }

    render(
      <MilkdownEditor
        document={docWithObjectContent}
        onSave={mockOnSave}
      />
    )

    expect(screen.getByText('Test Document')).toBeTruthy()
  })

  it('should handle string content', async () => {
    const docWithStringContent = {
      ...mockDocument,
      content: 'Just a plain string content'
    }

    render(
      <MilkdownEditor
        document={docWithStringContent}
        onSave={mockOnSave}
      />
    )

    expect(screen.getByText('Test Document')).toBeTruthy()
  })

  it('should handle dark mode', async () => {
    render(
      <MilkdownEditor
        document={mockDocument}
        onSave={mockOnSave}
        isDarkMode={true}
      />
    )

    const editorDiv = screen.getByText('Test Document').closest('.milkdown-editor')
    expect(editorDiv).toBeTruthy()
  })
})