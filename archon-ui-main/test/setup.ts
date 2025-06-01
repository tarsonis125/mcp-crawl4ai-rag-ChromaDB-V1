import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Setup file for Vitest with React Testing Library
// This file is automatically loaded before each test 

// Mock scrollIntoView which is not available in jsdom
Element.prototype.scrollIntoView = vi.fn(); 