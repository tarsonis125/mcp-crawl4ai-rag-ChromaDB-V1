import React, { useState } from 'react'
import {
  Trash2,
  X,
  RefreshCw,
  FileText,
  Globe,
  Code,
  Upload,
  Link as LinkIcon,
  Brain,
  BoxIcon,
  ChevronRight,
} from 'lucide-react'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { KnowledgeItem } from '../../types/knowledge'
import { useCardTilt } from '../../hooks/useCardTilt'
import '../../styles/card-animations.css'
import { TagsDisplay } from './TagsDisplay'
import { CodeViewerModal, CodeExample } from '../code/CodeViewerModal'
interface DeleteConfirmModalProps {
  onConfirm: () => void
  onCancel: () => void
  title: string
  message: string
}
export const DeleteConfirmModal = ({
  onConfirm,
  onCancel,
  title,
  message,
}: DeleteConfirmModalProps) => {
  return (
    <div className="fixed inset-0 bg-gray-500/50 dark:bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="w-full max-w-md">
        <Card className="w-full">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white mb-4">
            {title}
          </h3>
          <p className="text-gray-600 dark:text-zinc-400 mb-6">{message}</p>
          <div className="flex justify-end gap-4">
            <button
              onClick={onCancel}
              className="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={onConfirm}
              className="px-4 py-2 bg-pink-500 text-white rounded-md hover:bg-pink-600 transition-colors"
            >
              Delete
            </button>
          </div>
        </Card>
      </div>
    </div>
  )
}
interface TagsDisplayProps {
  tags: string[]
}
export const TagsDisplay = ({ tags }: TagsDisplayProps) => {
  const [showTooltip, setShowTooltip] = useState(false)
  if (!tags || tags.length === 0) return null
  // Limit to first 4 tags to ensure we stay within 2 rows (approximate)
  const visibleTags = tags.slice(0, 4)
  const remainingTags = tags.slice(4)
  const hasMoreTags = remainingTags.length > 0
  return (
    <div className="w-full">
      <div className="flex flex-wrap gap-2 h-full">
        {visibleTags.map((tag, index) => (
          <Badge
            key={index}
            color="purple"
            variant="outline"
            className="text-xs"
          >
            {tag}
          </Badge>
        ))}
        {hasMoreTags && (
          <div
            className="cursor-pointer relative"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
          >
            <Badge
              color="purple"
              variant="outline"
              className="bg-purple-100/50 dark:bg-purple-900/30 border-dashed text-xs"
            >
              +{remainingTags.length} more...
            </Badge>
            {showTooltip && (
              <div className="absolute top-full mt-2 left-1/2 transform -translate-x-1/2 bg-black dark:bg-zinc-800 text-white text-xs rounded-lg py-2 px-3 shadow-lg z-50 whitespace-nowrap max-w-xs">
                <div className="font-semibold text-purple-300 mb-1">
                  Additional Tags:
                </div>
                {remainingTags.map((tag, index) => (
                  <div key={index} className="text-gray-300">
                    • {tag}
                  </div>
                ))}
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-b-black dark:border-b-zinc-800"></div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
interface GroupedKnowledgeItemCardProps {
  groupedItem: {
    id: string
    title: string
    domain: string
    items: KnowledgeItem[]
    tags?: string[]
    description?: string
    status: string
    knowledgeType: string
    sourceType: string
    lastUpdated: string
    metadata: {
      wordCount: number
      updateFrequency: number
      codeExamples?: {
        count: number
        summaries: Array<{
          title: string
          description: string
        }>
      }
    }
  }
  onDelete: (sourceId: string) => void
}
export const GroupedKnowledgeItemCard = ({
  groupedItem,
  onDelete,
}: GroupedKnowledgeItemCardProps) => {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [showTooltip, setShowTooltip] = useState(false)
  const [showCodeTooltip, setShowCodeTooltip] = useState(false)
  const [isRemoving, setIsRemoving] = useState(false)
  const isGrouped = groupedItem.items.length > 1
  const firstItem = groupedItem.items[0]
  // Determine card properties based on the primary item
  const accentColor = groupedItem.sourceType === 'url' ? 'blue' : 'pink'
  const TypeIcon = groupedItem.knowledgeType === 'technical' ? BoxIcon : Brain
  const typeIconColor =
    groupedItem.knowledgeType === 'technical'
      ? 'text-blue-500'
      : 'text-purple-500'
  const statusColorMap = {
    active: 'green',
    processing: 'blue',
    error: 'pink',
  }
  // Use the tilt effect hook - remove soundEnabled
  const { cardRef, tiltStyles, handlers } = useCardTilt({
    max: 10,
    scale: 1.02,
    perspective: 1200,
  })
  const handleDelete = () => {
    setIsRemoving(true)
    // Delay the actual deletion to allow for the animation
    setTimeout(() => {
      onDelete(groupedItem.id)
      setShowDeleteConfirm(false)
    }, 500)
  }
  // Get frequency display for the primary item
  const getFrequencyDisplay = () => {
    const frequency = groupedItem.metadata.updateFrequency
    if (!frequency || frequency === 0) {
      return {
        icon: <X className="w-3 h-3" />,
        text: 'Never',
        color: 'text-gray-500 dark:text-zinc-500',
      }
    } else if (frequency === 1) {
      return {
        icon: <RefreshCw className="w-3 h-3" />,
        text: 'Daily',
        color: 'text-green-500',
      }
    } else if (frequency === 7) {
      return {
        icon: <RefreshCw className="w-3 h-3" />,
        text: 'Weekly',
        color: 'text-blue-500',
      }
    } else if (frequency === 30) {
      return {
        icon: <RefreshCw className="w-3 h-3" />,
        text: 'Monthly',
        color: 'text-purple-500',
      }
    } else {
      return {
        icon: <RefreshCw className="w-3 h-3" />,
        text: `Every ${frequency} days`,
        color: 'text-gray-500 dark:text-zinc-500',
      }
    }
  }
  const frequencyDisplay = getFrequencyDisplay()
  // Calculate total word count
  const totalWordCount = groupedItem.metadata.wordCount
  // Calculate total code examples count
  const totalCodeExamples = groupedItem.items.reduce(
    (sum, item) => sum + (item.metadata.codeExamples?.count || 0),
    0,
  )
  // Get code examples from all items in the group
  const allCodeExamples = groupedItem.items.reduce(
    (examples, item) => {
      if (item.metadata.codeExamples?.summaries) {
        return [...examples, ...item.metadata.codeExamples.summaries]
      }
      return examples
    },
    [] as Array<{
      title: string
      description: string
    }>,
  )
  return (
    <div
      ref={cardRef}
      className={`card-3d relative h-full ${isRemoving ? 'card-removing' : ''}`}
      style={{
        transform: tiltStyles.transform,
        transition: tiltStyles.transition,
      }}
      {...handlers}
    >
      <Card
        accentColor={accentColor}
        className="relative h-full flex flex-col overflow-hidden"
      >
        {/* Reflection overlay */}
        <div
          className="card-reflection"
          style={{
            opacity: tiltStyles.reflectionOpacity,
            backgroundPosition: tiltStyles.reflectionPosition,
          }}
        ></div>
        {/* Glow effect */}
        <div
          className={`card-glow card-glow-${accentColor}`}
          style={{
            opacity: tiltStyles.glowIntensity * 0.3,
            background: `radial-gradient(circle at ${tiltStyles.glowPosition.x}% ${tiltStyles.glowPosition.y}%, 
              rgba(${accentColor === 'blue' ? '59, 130, 246' : '236, 72, 153'}, 0.6) 0%, 
              rgba(${accentColor === 'blue' ? '59, 130, 246' : '236, 72, 153'}, 0) 70%)`,
          }}
        ></div>
        {/* Content container with proper z-index and flex layout */}
        <div className="relative z-10 flex flex-col h-full">
          {/* Header section - fixed height */}
          <div className="flex items-center gap-2 mb-3 card-3d-layer-1">
            {/* Source type icon */}
            {groupedItem.sourceType === 'url' ? (
              <LinkIcon className="w-4 h-4 text-blue-500" />
            ) : (
              <Upload className="w-4 h-4 text-pink-500" />
            )}
            {/* Knowledge type icon */}
            <TypeIcon className={`w-4 h-4 ${typeIconColor}`} />
            <h3 className="text-gray-800 dark:text-white font-medium flex-1 line-clamp-1">
              {isGrouped ? groupedItem.domain : groupedItem.title}
            </h3>
            <div className="flex items-center gap-1">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setShowDeleteConfirm(true)
                }}
                className="p-1 text-gray-500 hover:text-red-500"
                title="Delete"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          </div>
          {/* Description section - fixed height */}
          <p className="text-gray-600 dark:text-zinc-400 text-sm mb-3 line-clamp-2 card-3d-layer-2">
            {isGrouped
              ? `${groupedItem.items.length} sources from ${groupedItem.domain}`
              : groupedItem.description || 'No description available'}
          </p>
          {/* Tags section - flexible height with flex-1 */}
          <div className="flex-1 flex flex-col card-3d-layer-2 min-h-[4rem]">
            <TagsDisplay tags={groupedItem.tags || []} />
          </div>
          {/* Footer section - anchored to bottom */}
          <div className="flex items-end justify-between mt-auto card-3d-layer-1">
            {/* Left side - frequency and updated stacked */}
            <div className="flex flex-col">
              <div
                className={`flex items-center gap-1 ${frequencyDisplay.color} mb-1`}
              >
                {frequencyDisplay.icon}
                <span className="text-sm font-medium">
                  {frequencyDisplay.text}
                </span>
              </div>
              <span className="text-xs text-gray-500 dark:text-zinc-500">
                Updated:{' '}
                {new Date(groupedItem.lastUpdated).toLocaleDateString()}
              </span>
            </div>
            {/* Right side - sources and status inline */}
            <div className="flex items-center gap-2">
              {/* Grouped sources chip - inline with status */}
              {isGrouped && (
                <div
                  className="cursor-pointer relative card-3d-layer-3"
                  onMouseEnter={() => setShowTooltip(true)}
                  onMouseLeave={() => setShowTooltip(false)}
                >
                  <div className="flex items-center gap-1 px-2 py-1 bg-blue-500/20 border border-blue-500/40 rounded-full backdrop-blur-sm shadow-[0_0_15px_rgba(59,130,246,0.3)] hover:shadow-[0_0_20px_rgba(59,130,246,0.5)] transition-all duration-300">
                    <Globe className="w-3 h-3 text-blue-400" />
                    <span className="text-xs text-blue-400 font-medium">
                      {groupedItem.items.length}
                    </span>
                  </div>
                  {/* Tooltip */}
                  {showTooltip && (
                    <div className="absolute bottom-full mb-2 left-1/2 transform -translate-x-1/2 bg-black dark:bg-zinc-800 text-white text-xs rounded-lg py-2 px-3 shadow-lg z-50 whitespace-nowrap max-w-xs">
                      <div className="font-semibold text-blue-300 mb-1">
                        Grouped Sources:
                      </div>
                      {groupedItem.items.map((item, index) => (
                        <div key={index} className="text-gray-300">
                          {index + 1}. {item.title}
                        </div>
                      ))}
                      <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-t-black dark:border-t-zinc-800"></div>
                    </div>
                  )}
                </div>
              )}
              {/* Code examples badge */}
              {totalCodeExamples > 0 && (
                <div
                  className="cursor-pointer relative card-3d-layer-3"
                  onMouseEnter={() => setShowCodeTooltip(true)}
                  onMouseLeave={() => setShowCodeTooltip(false)}
                >
                  <div className="flex items-center gap-1 px-2 py-1 bg-pink-500/20 border border-pink-500/40 rounded-full backdrop-blur-sm shadow-[0_0_15px_rgba(236,72,153,0.3)] hover:shadow-[0_0_20px_rgba(236,72,153,0.5)] transition-all duration-300">
                    <Code className="w-3 h-3 text-pink-400" />
                    <span className="text-xs text-pink-400 font-medium">
                      {totalCodeExamples}
                    </span>
                  </div>
                  {/* Code Examples Tooltip */}
                  {showCodeTooltip && (
                    <div className="absolute bottom-full mb-2 left-1/2 transform -translate-x-1/2 bg-black dark:bg-zinc-800 text-white text-xs rounded-lg py-2 px-3 shadow-lg z-50 max-w-xs">
                      <div className="font-semibold text-pink-300 mb-1">
                        Code Examples:
                      </div>
                      <div className="max-h-48 overflow-y-auto">
                        {allCodeExamples.length > 0 ? (
                          allCodeExamples.map((example, index) => (
                            <div key={index} className="mb-2 last:mb-0">
                              <div className="text-pink-200 font-medium">
                                {example.title}
                              </div>
                              <div className="text-gray-300 text-xs">
                                {example.description}
                              </div>
                            </div>
                          ))
                        ) : (
                          <div className="text-gray-300">
                            {totalCodeExamples} code examples
                          </div>
                        )}
                      </div>
                      <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-t-black dark:border-t-zinc-800"></div>
                    </div>
                  )}
                </div>
              )}
              {/* Page count - orange neon container */}
              <div className="relative group card-3d-layer-3">
                <div className="flex items-center gap-1 px-2 py-1 bg-orange-500/20 border border-orange-500/40 rounded-full backdrop-blur-sm shadow-[0_0_15px_rgba(251,146,60,0.3)] transition-all duration-300 cursor-help">
                  <FileText className="w-3 h-3 text-orange-400" />
                  <span className="text-xs text-orange-400 font-medium">
                    {Math.ceil(totalWordCount / 250).toLocaleString()}
                  </span>
                </div>
                {/* Tooltip */}
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-200 z-50">
                  <div className="bg-black dark:bg-zinc-800 text-white text-xs px-3 py-2 rounded-lg shadow-lg whitespace-nowrap">
                    <div className="font-medium mb-1">
                      {totalWordCount.toLocaleString()} words
                    </div>
                    <div className="text-gray-300 space-y-0.5">
                      <div>
                        = {Math.ceil(totalWordCount / 250).toLocaleString()}{' '}
                        pages
                      </div>
                      <div>
                        = {(totalWordCount / 80000).toFixed(1)} average novels
                      </div>
                    </div>
                    <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-t-black dark:border-t-zinc-800"></div>
                  </div>
                </div>
              </div>
              <Badge
                color={statusColorMap[groupedItem.status || 'active'] as any}
                className="card-3d-layer-2"
              >
                {(groupedItem.status || 'active').charAt(0).toUpperCase() +
                  (groupedItem.status || 'active').slice(1)}
              </Badge>
            </div>
          </div>
        </div>
      </Card>
      {showDeleteConfirm && (
        <DeleteConfirmModal
          onConfirm={handleDelete}
          onCancel={() => setShowDeleteConfirm(false)}
          title={isGrouped ? 'Delete Grouped Sources' : 'Delete Knowledge Item'}
          message={
            isGrouped
              ? `Are you sure you want to delete all ${groupedItem.items.length} sources from ${groupedItem.domain}? This action cannot be undone.`
              : 'Are you sure you want to delete this knowledge item? This action cannot be undone.'
          }
        />
      )}
    </div>
  )
}
interface KnowledgeItemCardProps {
  item: KnowledgeItem
  viewMode: 'grid' | 'list'
  onDelete: (sourceId: string) => void
}
export const KnowledgeItemCard = ({
  item,
  viewMode,
  onDelete,
}: KnowledgeItemCardProps) => {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [showCodeTooltip, setShowCodeTooltip] = useState(false)
  const [isRemoving, setIsRemoving] = useState(false)
  const [showTooltip, setShowTooltip] = useState(false)
  const [showCodeModal, setShowCodeModal] = useState(false)
  const statusColorMap = {
    active: 'green',
    processing: 'blue',
    error: 'pink',
  }
  const accentColor = item.sourceType === 'url' ? 'blue' : 'pink'
  // Get the type icon
  const TypeIcon = item.knowledgeType === 'technical' ? BoxIcon : Brain
  const typeIconColor =
    item.knowledgeType === 'technical' ? 'text-blue-500' : 'text-purple-500'
  // Use the tilt effect hook - different settings for list vs grid view
  const { cardRef, tiltStyles, handlers } = useCardTilt({
    max: viewMode === 'grid' ? 10 : 5,
    scale: viewMode === 'grid' ? 1.02 : 1.01,
    perspective: 1200,
  })
  const handleDelete = () => {
    setIsRemoving(true)
    // Delay the actual deletion to allow for the animation
    setTimeout(() => {
      onDelete(item.id)
      setShowDeleteConfirm(false)
    }, 500)
  }
  // Get frequency display
  const getFrequencyDisplay = () => {
    const frequency = item.metadata.updateFrequency
    if (!frequency || frequency === 0) {
      return {
        icon: <X className="w-3 h-3" />,
        text: 'Never',
        color: 'text-gray-500 dark:text-zinc-500',
      }
    } else if (frequency === 1) {
      return {
        icon: <RefreshCw className="w-3 h-3" />,
        text: 'Daily',
        color: 'text-green-500',
      }
    } else if (frequency === 7) {
      return {
        icon: <RefreshCw className="w-3 h-3" />,
        text: 'Weekly',
        color: 'text-blue-500',
      }
    } else if (frequency === 30) {
      return {
        icon: <RefreshCw className="w-3 h-3" />,
        text: 'Monthly',
        color: 'text-purple-500',
      }
    } else {
      return {
        icon: <RefreshCw className="w-3 h-3" />,
        text: `Every ${frequency} days`,
        color: 'text-gray-500 dark:text-zinc-500',
      }
    }
  }
  const frequencyDisplay = getFrequencyDisplay()
  // Get code examples count
  const codeExamplesCount = item.metadata.codeExamples?.count || 0
  // Format code examples for the modal
  const codeExamples: CodeExample[] =
    item.metadata.codeExamples?.summaries?.map((example, index) => ({
      id: `${item.id}-example-${index}`,
      title: example.title || 'Untitled Example',
      description: example.description || 'No description available',
      language: example.language || guessLanguageFromTitle(example.title || ''),
      code: example.code || '// Code example not available',
      tags: example.tags || [],
    })) || []
  if (viewMode === 'list') {
    return (
      <div
        ref={cardRef}
        className={`card-3d relative ${isRemoving ? 'card-removing' : ''}`}
        style={{
          transform: tiltStyles.transform,
          transition: tiltStyles.transition,
        }}
        {...handlers}
      >
        <Card
          accentColor={accentColor}
          className="flex items-center gap-4 overflow-hidden relative z-10"
        >
          {/* Reflection overlay */}
          <div
            className="card-reflection"
            style={{
              opacity: tiltStyles.reflectionOpacity,
              backgroundPosition: tiltStyles.reflectionPosition,
            }}
          ></div>
          {/* Glow effect */}
          <div
            className="absolute inset-0 rounded-md z-0"
            style={{
              opacity: tiltStyles.glowIntensity * 0.3,
              background: `radial-gradient(circle at ${tiltStyles.glowPosition.x}% ${tiltStyles.glowPosition.y}%, 
                rgba(${accentColor === 'blue' ? '59, 130, 246' : '236, 72, 153'}, 0.6) 0%, 
                rgba(${accentColor === 'blue' ? '59, 130, 246' : '236, 72, 153'}, 0) 70%)`,
              boxShadow: `0 0 20px 5px rgba(${accentColor === 'blue' ? '59, 130, 246' : '236, 72, 153'}, 0.3)`,
            }}
          ></div>
          <div className="flex-1 card-3d-content relative z-10">
            <div className="flex items-center gap-2 mb-2">
              {/* Source type icon */}
              {item.sourceType === 'url' ? (
                <LinkIcon className="w-4 h-4 text-blue-500" />
              ) : (
                <Upload className="w-4 h-4 text-pink-500" />
              )}
              {/* Knowledge type icon */}
              <TypeIcon className={`w-4 h-4 ${typeIconColor}`} />
              <h3 className="text-gray-800 dark:text-white font-medium">
                {item.title}
              </h3>
              <div className="ml-auto">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setShowDeleteConfirm(true)
                  }}
                  className="p-1 text-gray-500 hover:text-red-500"
                  title="Delete"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </div>
            <p className="text-gray-600 dark:text-zinc-400 text-sm mb-2">
              {item.description}
            </p>
            <div className="flex flex-wrap gap-2 mb-2">
              <TagsDisplay tags={item.tags || []} />
            </div>
            <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-zinc-500">
              <span>Last updated: {item.lastUpdated}</span>
              <div
                className={`flex items-center gap-1 ${frequencyDisplay.color}`}
              >
                {frequencyDisplay.icon}
                <span>{frequencyDisplay.text}</span>
              </div>
              {/* Code examples badge for list view */}
              {codeExamplesCount > 0 && (
                <div
                  className="relative"
                  onMouseEnter={() => setShowCodeTooltip(true)}
                  onMouseLeave={() => setShowCodeTooltip(false)}
                >
                  <div className="flex items-center gap-1 text-pink-500">
                    <Code className="w-3 h-3" />
                    <span>{codeExamplesCount} code examples</span>
                  </div>
                  {/* Code Examples Tooltip for list view */}
                  {showCodeTooltip && (
                    <div className="absolute bottom-full mb-2 left-0 bg-black dark:bg-zinc-800 text-white text-xs rounded-lg py-2 px-3 shadow-lg z-50 max-w-xs">
                      <div className="font-semibold text-pink-300 mb-1">
                        Code Examples:
                      </div>
                      <div className="max-h-48 overflow-y-auto">
                        {item.metadata.codeExamples?.summaries?.map(
                          (example, index) => (
                            <div key={index} className="mb-2 last:mb-0">
                              <div className="text-pink-200 font-medium">
                                {example.title}
                              </div>
                              <div className="text-gray-300 text-xs">
                                {example.description}
                              </div>
                            </div>
                          ),
                        )}
                      </div>
                      <div className="absolute top-full left-4 border-4 border-transparent border-t-black dark:border-t-zinc-800"></div>
                    </div>
                  )}
                </div>
              )}
              <Badge color={statusColorMap[item.status] as any}>
                {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
              </Badge>
            </div>
          </div>
          {/* Add code examples modal */}
          {showCodeModal && codeExamples.length > 0 && (
            <CodeViewerModal
              examples={codeExamples}
              onClose={() => setShowCodeModal(false)}
            />
          )}
          {showDeleteConfirm && (
            <DeleteConfirmModal
              onConfirm={handleDelete}
              onCancel={() => setShowDeleteConfirm(false)}
              title="Delete Knowledge Item"
              message="Are you sure you want to delete this knowledge item? This action cannot be undone."
            />
          )}
        </Card>
      </div>
    )
  }
  return (
    <div
      ref={cardRef}
      className={`card-3d relative h-full ${isRemoving ? 'card-removing' : ''}`}
      style={{
        transform: tiltStyles.transform,
        transition: tiltStyles.transition,
      }}
      {...handlers}
    >
      <Card
        accentColor={accentColor}
        className="h-full flex flex-col overflow-hidden relative z-10"
      >
        {/* Reflection overlay */}
        <div
          className="card-reflection"
          style={{
            opacity: tiltStyles.reflectionOpacity,
            backgroundPosition: tiltStyles.reflectionPosition,
          }}
        ></div>
        {/* Glow effect */}
        <div
          className="absolute inset-0 rounded-md z-0"
          style={{
            opacity: tiltStyles.glowIntensity * 0.3,
            background: `radial-gradient(circle at ${tiltStyles.glowPosition.x}% ${tiltStyles.glowPosition.y}%, 
              rgba(${accentColor === 'blue' ? '59, 130, 246' : '236, 72, 153'}, 0.6) 0%, 
              rgba(${accentColor === 'blue' ? '59, 130, 246' : '236, 72, 153'}, 0) 70%)`,
            boxShadow: `0 0 20px 5px rgba(${accentColor === 'blue' ? '59, 130, 246' : '236, 72, 153'}, 0.3)`,
          }}
        ></div>
        {/* Content container with proper z-index */}
        <div className="relative z-10 flex flex-col h-full">
          {/* Header section */}
          <div className="flex items-center gap-2 mb-3 card-3d-layer-1">
            {/* Source type icon */}
            {item.sourceType === 'url' ? (
              <LinkIcon className="w-4 h-4 text-blue-500" />
            ) : (
              <Upload className="w-4 h-4 text-pink-500" />
            )}
            {/* Knowledge type icon */}
            <TypeIcon className={`w-4 h-4 ${typeIconColor}`} />
            <h3 className="text-gray-800 dark:text-white font-medium flex-1 line-clamp-1">
              {item.title}
            </h3>
            <div className="flex items-center gap-1">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setShowDeleteConfirm(true)
                }}
                className="p-1 text-gray-500 hover:text-red-500"
                title="Delete"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          </div>
          {/* Description section */}
          <p className="text-gray-600 dark:text-zinc-400 text-sm mb-3 line-clamp-2 card-3d-layer-2">
            {item.description || 'No description available'}
          </p>
          {/* Tags section - flexible height with flex-1 to expand */}
          <div className="flex-1 flex flex-col card-3d-layer-2 min-h-[4rem]">
            <TagsDisplay tags={item.tags || []} />
          </div>
          {/* Footer section - anchored to bottom */}
          <div className="flex items-end justify-between mt-2 card-3d-layer-1">
            {/* Left side - frequency and updated stacked */}
            <div className="flex flex-col">
              <div
                className={`flex items-center gap-1 ${frequencyDisplay.color} mb-1`}
              >
                {frequencyDisplay.icon}
                <span className="text-sm font-medium">
                  {frequencyDisplay.text}
                </span>
              </div>
              <span className="text-xs text-gray-500 dark:text-zinc-500">
                Updated: {new Date(item.lastUpdated).toLocaleDateString()}
              </span>
            </div>
            {/* Right side - code examples, page count and status */}
            <div className="flex items-center gap-2">
              {/* Code examples badge */}
              {codeExamplesCount > 0 && (
                <div
                  className="cursor-pointer relative card-3d-layer-3"
                  onClick={() => setShowCodeModal(true)}
                  onMouseEnter={() => setShowCodeTooltip(true)}
                  onMouseLeave={() => setShowCodeTooltip(false)}
                >
                  <div className="flex items-center gap-1 px-2 py-1 bg-pink-500/20 border border-pink-500/40 rounded-full backdrop-blur-sm shadow-[0_0_15px_rgba(236,72,153,0.3)] hover:shadow-[0_0_20px_rgba(236,72,153,0.5)] transition-all duration-300">
                    <Code className="w-3 h-3 text-pink-400" />
                    <span className="text-xs text-pink-400 font-medium">
                      {codeExamplesCount}
                    </span>
                  </div>
                  {/* ... existing tooltip ... */}
                </div>
              )}
              {/* Page count - orange neon container */}
              <div className="relative group card-3d-layer-3">
                <div className="flex items-center gap-1 px-2 py-1 bg-orange-500/20 border border-orange-500/40 rounded-full backdrop-blur-sm shadow-[0_0_15px_rgba(251,146,60,0.3)] transition-all duration-300 cursor-help">
                  <FileText className="w-3 h-3 text-orange-400" />
                  <span className="text-xs text-orange-400 font-medium">
                    {Math.ceil(
                      (item.metadata.wordCount || 0) / 250,
                    ).toLocaleString()}
                  </span>
                </div>
                {/* Tooltip */}
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-200 z-50">
                  <div className="bg-black dark:bg-zinc-800 text-white text-xs px-3 py-2 rounded-lg shadow-lg whitespace-nowrap">
                    <div className="font-medium mb-1">
                      {item.metadata.wordCount?.toLocaleString() || 0} words
                    </div>
                    <div className="text-gray-300 space-y-0.5">
                      <div>
                        ={' '}
                        {Math.ceil(
                          (item.metadata.wordCount || 0) / 250,
                        ).toLocaleString()}{' '}
                        pages
                      </div>
                      <div>
                        = {((item.metadata.wordCount || 0) / 80000).toFixed(1)}{' '}
                        average novels
                      </div>
                    </div>
                    <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-t-black dark:border-t-zinc-800"></div>
                  </div>
                </div>
              </div>
              <Badge
                color={statusColorMap[item.status] as any}
                className="card-3d-layer-2"
              >
                {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
              </Badge>
            </div>
          </div>
        </div>
      </Card>
      {/* Code Examples Modal */}
      {showCodeModal && codeExamples.length > 0 && (
        <CodeViewerModal
          examples={codeExamples}
          onClose={() => setShowCodeModal(false)}
        />
      )}
      {showDeleteConfirm && (
        <DeleteConfirmModal
          onConfirm={handleDelete}
          onCancel={() => setShowDeleteConfirm(false)}
          title="Delete Knowledge Item"
          message="Are you sure you want to delete this knowledge item? This action cannot be undone."
        />
      )}
    </div>
  )
}
// Helper function to guess language from title
const guessLanguageFromTitle = (title: string = ''): string => {
  const titleLower = title.toLowerCase()
  if (titleLower.includes('javascript') || titleLower.includes('js'))
    return 'javascript'
  if (titleLower.includes('typescript') || titleLower.includes('ts'))
    return 'typescript'
  if (titleLower.includes('react')) return 'jsx'
  if (titleLower.includes('html')) return 'html'
  if (titleLower.includes('css')) return 'css'
  if (titleLower.includes('python')) return 'python'
  if (titleLower.includes('java')) return 'java'
  return 'javascript' // Default
}
