import React, { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { motion } from 'framer-motion'
import {
  X,
  Copy,
  Check,
  Code as CodeIcon,
  FileText,
  TagIcon,
  Info,
} from 'lucide-react'
import Prism from 'prismjs'
import 'prismjs/components/prism-javascript'
import 'prismjs/components/prism-jsx'
import 'prismjs/components/prism-typescript'
import 'prismjs/components/prism-tsx'
import 'prismjs/components/prism-css'
import 'prismjs/components/prism-python'
import 'prismjs/components/prism-java'
import 'prismjs/components/prism-json'
import 'prismjs/components/prism-markdown'
import 'prismjs/components/prism-yaml'
import 'prismjs/components/prism-bash'
import 'prismjs/components/prism-sql'
import 'prismjs/components/prism-graphql'
import 'prismjs/themes/prism-tomorrow.css'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
export interface CodeExample {
  id: string
  title: string
  description: string
  language: string
  code: string
  tags?: string[]
}
interface CodeViewerModalProps {
  examples: CodeExample[]
  onClose: () => void
}
export const CodeViewerModal: React.FC<CodeViewerModalProps> = ({
  examples,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<'code' | 'metadata'>('code')
  const [activeExampleIndex, setActiveExampleIndex] = useState(0)
  const [copied, setCopied] = useState(false)
  const activeExample = examples[activeExampleIndex]
  // Handle escape key to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])
  // Apply syntax highlighting
  useEffect(() => {
    if (activeExample) {
      Prism.highlightAll()
    }
  }, [activeExample, activeExampleIndex])
  const handleCopyCode = () => {
    if (activeExample) {
      navigator.clipboard.writeText(activeExample.code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }
  // Using React Portal to render the modal at the root level
  return createPortal(
    <motion.div
      initial={{
        opacity: 0,
      }}
      animate={{
        opacity: 1,
      }}
      exit={{
        opacity: 0,
      }}
      className="fixed inset-0 flex items-center justify-center z-50"
    >
      <motion.div
        initial={{
          scale: 0.9,
          opacity: 0,
        }}
        animate={{
          scale: 1,
          opacity: 1,
        }}
        exit={{
          scale: 0.9,
          opacity: 0,
        }}
        className="relative bg-black/40 border border-gray-800 rounded-lg w-full max-w-6xl h-[80vh] flex flex-col overflow-hidden backdrop-blur-sm"
      >
        {/* Neon accent line at the top */}
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-green-500 shadow-[0_0_20px_5px_rgba(16,185,129,0.7)]"></div>
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b border-gray-800">
          <div>
            <h2 className="text-2xl font-bold text-green-400">Code Examples</h2>
            <p className="text-gray-400 mt-1 max-w-2xl">
              {activeExample.description}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-white bg-black/50 border border-gray-800 rounded-full p-2 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        {/* File Selector */}
        <div className="flex justify-between items-center p-4 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <select
              className="bg-gray-900 border border-gray-800 rounded text-sm text-gray-300 px-2 py-1"
              value={activeExampleIndex}
              onChange={(e) => setActiveExampleIndex(Number(e.target.value))}
            >
              {examples.map((example, index) => (
                <option key={example.id} value={index}>
                  {example.title}
                </option>
              ))}
            </select>
            <div className="flex items-center gap-2 ml-4">
              <Badge color="green" variant="outline" className="text-xs">
                {activeExample.language}
              </Badge>
              {activeExample.tags?.map((tag) => (
                <Badge
                  key={tag}
                  color="gray"
                  variant="outline"
                  className="flex items-center gap-1 text-xs"
                >
                  <TagIcon className="w-3 h-3" />
                  {tag}
                </Badge>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              accentColor="green"
              size="sm"
              onClick={handleCopyCode}
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4 mr-2" />
                  <span>Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4 mr-2" />
                  <span>Copy Code</span>
                </>
              )}
            </Button>
          </div>
        </div>
        {/* Tabs */}
        <div className="flex border-b border-gray-800">
          <TabButton
            active={activeTab === 'code'}
            onClick={() => setActiveTab('code')}
            icon={<CodeIcon className="w-4 h-4" />}
            label="Code"
            color="green"
          />
          <TabButton
            active={activeTab === 'metadata'}
            onClick={() => setActiveTab('metadata')}
            icon={<Info className="w-4 h-4" />}
            label="Metadata"
            color="green"
          />
        </div>
        {/* Content */}
        <div className="flex-1 overflow-auto">
          {activeTab === 'code' && (
            <div className="h-full p-4">
              <div className="bg-[#2d2d2d] rounded-lg border border-gray-800 h-full overflow-auto">
                <pre className="p-4 text-sm">
                  <code
                    className={`language-${activeExample.language || 'javascript'}`}
                  >
                    {activeExample.code}
                  </code>
                </pre>
              </div>
            </div>
          )}
          {activeTab === 'metadata' && (
            <div className="h-full p-4">
              <div className="bg-gray-900/70 rounded-lg border border-gray-800 p-6 h-full overflow-auto">
                <h3 className="text-lg font-medium text-green-400 mb-4">
                  {activeExample.title} Metadata
                </h3>
                <p className="text-gray-300 mb-4">
                  {activeExample.description}
                </p>
                <div className="mb-6">
                  <h4 className="text-md font-medium text-gray-300 mb-2">
                    Language:{' '}
                    <span className="text-green-400">
                      {activeExample.language}
                    </span>
                  </h4>
                  <p className="text-gray-400">
                    This example demonstrates a common pattern in{' '}
                    {activeExample.language} development.
                  </p>
                </div>
                {activeExample.tags && activeExample.tags.length > 0 && (
                  <div>
                    <h4 className="text-md font-medium text-gray-300 mb-2">
                      Tags
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {activeExample.tags.map((tag) => (
                        <Badge key={tag} color="green" variant="outline">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>,
    document.body,
  )
}
interface TabButtonProps {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
  color: string
}
const TabButton: React.FC<TabButtonProps> = ({
  active,
  onClick,
  icon,
  label,
  color,
}) => {
  const colorMap: Record<string, string> = {
    green: 'text-green-400 border-green-500',
    blue: 'text-blue-400 border-blue-500',
    pink: 'text-pink-400 border-pink-500',
    purple: 'text-purple-400 border-purple-500',
  }
  const activeColor = colorMap[color] || 'text-green-400 border-green-500'
  return (
    <button
      onClick={onClick}
      className={`
        px-6 py-3 flex items-center gap-2 transition-all duration-300 relative
        ${active ? activeColor : 'text-gray-400 hover:text-gray-200 border-transparent'}
      `}
    >
      {icon}
      {label}
      {active && (
        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-green-500"></div>
      )}
    </button>
  )
}
