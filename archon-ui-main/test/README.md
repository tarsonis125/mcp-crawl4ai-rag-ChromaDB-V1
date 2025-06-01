# Test Directory Structure

This directory contains all test files for the Archon UI application, following Vite/Vitest best practices.

## Structure

```
test/
├── setup.ts          # Global test setup and configuration
├── App.test.tsx      # Root component tests
├── pages/            # Page component tests
│   └── MCPPage.test.tsx
└── services/         # Service layer tests
    ├── api.test.ts
    └── mcpService.test.ts
```

## Running Tests

```bash
# Run tests in watch mode
npm test

# Run tests with UI
npm run test:ui

# Run tests with coverage
npm run test:coverage
```

## Writing Tests

- Test files should mirror the src directory structure
- Use `.test.ts` or `.test.tsx` extensions
- Import components/services using the `@/` alias (maps to `src/`)
- Mock external dependencies and API calls
- Follow the AAA pattern: Arrange, Act, Assert

## Example Test

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MyComponent } from '@/components/MyComponent'

describe('MyComponent', () => {
  it('should render correctly', () => {
    render(<MyComponent />)
    expect(screen.getByText('Hello')).toBeInTheDocument()
  })
})
``` 