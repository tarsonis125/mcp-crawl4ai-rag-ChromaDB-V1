import React, { useMemo, useState } from 'react'
// ... existing imports ...
import { TagsDisplay } from './TagsDisplay'
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
import { useCardTilt } from '../../hooks/useCardTilt'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { DeleteConfirmModal } from './KnowledgeItemCard'
import { CodeViewerModal, CodeExample } from '../code/CodeViewerModal'
// Helper function to guess language from title - moved to the top to ensure it's defined before use
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
export const GroupedKnowledgeItemCard = ({
  groupedItem,
  onDelete,
  enableSoundEffects = false,
}: GroupedKnowledgeItemCardProps) => {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [showTooltip, setShowTooltip] = useState(false)
  const [showCodeTooltip, setShowCodeTooltip] = useState(false)
  const [isRemoving, setIsRemoving] = useState(false)
  const [activeCardIndex, setActiveCardIndex] = useState(0)
  const [isShuffling, setIsShuffling] = useState(false)
  const [showCodeModal, setShowCodeModal] = useState(false)
  const isGrouped = groupedItem.items.length > 1
  const activeItem = groupedItem.items[activeCardIndex]
  // Determine card properties based on the active item
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
  // Use the tilt effect hook - but only apply the handlers if not grouped
  const { cardRef, tiltStyles, handlers } = useCardTilt({
    max: 10,
    scale: 1.02,
    perspective: 1200,
  })
  // Only use tilt handlers if not grouped
  const tiltHandlers = isGrouped ? {} : handlers
  const handleDelete = () => {
    setIsRemoving(true)
    // Delay the actual deletion to allow for the animation
    setTimeout(() => {
      onDelete(groupedItem.id)
      setShowDeleteConfirm(false)
    }, 500)
  }
  // Get frequency display for the active item
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
  const totalCodeExamples = useMemo(() => {
    return groupedItem.items.reduce(
      (sum, item) => sum + (item?.metadata?.codeExamples?.count || 0),
      0,
    )
  }, [groupedItem.items])
  // Get code examples from all items in the group
  const allCodeExamples = useMemo(() => {
    return groupedItem.items.reduce(
      (examples, item) => {
        if (item?.metadata?.codeExamples?.summaries) {
          return [...examples, ...item.metadata.codeExamples.summaries]
        }
        return examples
      },
      [] as Array<{
        title: string
        description: string
      }>,
    )
  }, [groupedItem.items])
  // Helper function to safely get code examples
  const getCodeExamples = (item: any): CodeExample[] => {
    if (
      !item ||
      !item.metadata ||
      !item.metadata.codeExamples ||
      !item.metadata.codeExamples.summaries
    ) {
      return []
    }
    return item.metadata.codeExamples.summaries.map(
      (example: any, index: number) => {
        if (!example)
          return {
            id: `${item.id || 'unknown'}-example-${index}`,
            title: 'Untitled Example',
            description: 'No description available',
            language: 'javascript',
            code: '// Code example not available',
            tags: [],
          }
        return {
          id: `${item.id || 'unknown'}-example-${index}`,
          title: example.title || 'Untitled Example',
          description: example.description || 'No description available',
          language:
            example.language || guessLanguageFromTitle(example.title || ''),
          code: example.code || '// Code example not available',
          tags: Array.isArray(example.tags) ? example.tags : [],
        }
      },
    )
  }
  // Format code examples for the modal with additional safety checks
  const formattedCodeExamples = useMemo(() => {
    if (
      !groupedItem ||
      !groupedItem.items ||
      !Array.isArray(groupedItem.items)
    ) {
      return []
    }
    return groupedItem.items.reduce((examples: CodeExample[], item) => {
      if (!item) return examples
      const itemExamples = getCodeExamples(item)
      return [...examples, ...itemExamples]
    }, [])
  }, [groupedItem?.items])
  // Function to shuffle to the next card
  const shuffleToNextCard = () => {
    if (!isGrouped || isShuffling) return
    setIsShuffling(true)
    const nextIndex = (activeCardIndex + 1) % groupedItem.items.length
    // Add a small delay to allow animation to complete
    setTimeout(() => {
      setActiveCardIndex(nextIndex)
      setIsShuffling(false)
    }, 300)
  }
  // Card content renderer - extracted to avoid duplication
  const renderCardContent = (item = activeItem) => (
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
        {/* Title with source count badge moved to header */}
        <div className="flex items-center flex-1 gap-2">
          <h3 className="text-gray-800 dark:text-white font-medium line-clamp-1">
            {item.title || groupedItem.domain}
          </h3>
          {/* Sources badge - moved to header */}
          {isGrouped && (
            <button
              onClick={shuffleToNextCard}
              className="group flex items-center gap-1 px-2 py-1 bg-blue-500/20 border border-blue-500/40 rounded-full backdrop-blur-sm shadow-[0_0_15px_rgba(59,130,246,0.3)] hover:shadow-[0_0_20px_rgba(59,130,246,0.5)] transition-all duration-300 card-3d-layer-3"
              onMouseEnter={() => setShowTooltip(true)}
              onMouseLeave={() => setShowTooltip(false)}
            >
              <Globe className="w-3 h-3 text-blue-400" />
              <span className="text-xs text-blue-400 font-medium">
                {activeCardIndex + 1}/{groupedItem.items.length}
              </span>
              <ChevronRight className="w-3 h-3 text-blue-400 group-hover:translate-x-0.5 transition-transform" />
            </button>
          )}
        </div>
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
        {item.description ||
          `Source ${activeCardIndex + 1} of ${groupedItem.items.length} from ${groupedItem.domain}`}
      </p>
      {/* Tags section - flexible height with flex-1 */}
      <div className="flex-1 flex flex-col card-3d-layer-2 min-h-[4rem]">
        <TagsDisplay tags={item.tags || []} />
      </div>
      {/* Footer section - anchored to bottom */}
      <div className="flex items-end justify-between mt-auto card-3d-layer-1">
        {/* Left side - frequency and updated stacked */}
        <div className="flex flex-col">
          <div
            className={`flex items-center gap-1 ${frequencyDisplay.color} mb-1`}
          >
            {frequencyDisplay.icon}
            <span className="text-sm font-medium">{frequencyDisplay.text}</span>
          </div>
          <span className="text-xs text-gray-500 dark:text-zinc-500">
            Updated: {new Date(groupedItem.lastUpdated).toLocaleDateString()}
          </span>
        </div>
        {/* Right side - code examples and status inline */}
        <div className="flex items-center gap-2">
          {/* Code examples badge */}
          {totalCodeExamples > 0 && (
            <div
              className="cursor-pointer relative card-3d-layer-3"
              onClick={() => setShowCodeModal(true)}
              onMouseEnter={() => setShowCodeTooltip(true)}
              onMouseLeave={() => setShowCodeTooltip(false)}
            >
              <div className="flex items-center gap-1 px-2 py-1 bg-pink-500/20 border border-pink-500/40 rounded-full backdrop-blur-sm shadow-[0_0_15px_rgba(236,72,153,0.3)] hover:shadow-[0_0_20px_rgba(236,72,153,0.5)] transition-all duration-300">
                <Code className="w-3 h-3 text-pink-400" />
                <span className="text-xs text-pink-400 font-medium">
                  {totalCodeExamples}
                </span>
              </div>
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
  )
  return (
    <div
      ref={cardRef}
      className={`relative h-full ${isRemoving ? 'card-removing' : ''}`}
      style={{
        transform: isGrouped ? 'perspective(1200px)' : tiltStyles.transform,
        transition: tiltStyles.transition,
        transformStyle: 'preserve-3d',
      }}
      {...tiltHandlers}
    >
      {/* Stacked cards effect - background cards */}
      {isGrouped && (
        <>
          {/* Third card (bottom of stack) */}
          <div
            className="absolute top-0 left-0 w-full h-full"
            style={{
              zIndex: 1,
              transform:
                'translateZ(-60px) translateY(-16px) translateX(-8px) rotateX(-2deg) rotateY(-2deg)',
              transformStyle: 'preserve-3d',
              filter: 'drop-shadow(0 10px 8px rgba(0, 0, 0, 0.15))',
            }}
          >
            <Card
              accentColor={accentColor}
              className="w-full h-full bg-white/60 dark:bg-zinc-900/60 backdrop-blur-md shadow-md opacity-60 overflow-hidden"
            >
              {/* Add a simplified version of the content for depth */}
              <div className="p-4 opacity-30">
                {renderCardContent(
                  groupedItem.items[
                    (activeCardIndex + groupedItem.items.length - 2) %
                      groupedItem.items.length
                  ],
                )}
              </div>
            </Card>
          </div>
          {/* Second card (middle of stack) */}
          <div
            className="absolute top-0 left-0 w-full h-full"
            style={{
              zIndex: 2,
              transform:
                'translateZ(-30px) translateY(-8px) translateX(-4px) rotateX(-1deg) rotateY(-1deg)',
              transformStyle: 'preserve-3d',
              filter: 'drop-shadow(0 8px 6px rgba(0, 0, 0, 0.1))',
            }}
          >
            <Card
              accentColor={accentColor}
              className="w-full h-full bg-white/70 dark:bg-zinc-900/70 backdrop-blur-md shadow-md opacity-80 overflow-hidden"
            >
              {/* Add a simplified version of the content for depth */}
              <div className="p-4 opacity-60">
                {renderCardContent(
                  groupedItem.items[
                    (activeCardIndex + groupedItem.items.length - 1) %
                      groupedItem.items.length
                  ],
                )}
              </div>
            </Card>
          </div>
        </>
      )}
      {/* Main card (top of stack) - with animation for shuffling */}
      <div
        className={`relative z-10 transition-all duration-300 h-full ${isShuffling ? 'animate-card-shuffle-out' : 'opacity-100 scale-100'}`}
        style={{
          transform: 'translateZ(0)',
          transformStyle: 'preserve-3d',
          filter: 'drop-shadow(0 4px 3px rgba(0, 0, 0, 0.07))',
        }}
      >
        <Card
          accentColor={accentColor}
          className="relative h-full flex flex-col backdrop-blur-lg bg-white/80 dark:bg-zinc-900/80"
        >
          {/* Reflection overlay */}
          <div
            className="card-reflection"
            style={{
              opacity: isGrouped ? 0 : tiltStyles.reflectionOpacity,
              backgroundPosition: tiltStyles.reflectionPosition,
            }}
          ></div>
          {/* Card content */}
          {renderCardContent()}
        </Card>
      </div>
      {/* Incoming card animation - only visible during shuffle */}
      {isShuffling && (
        <div
          className="absolute inset-0 z-20 animate-card-shuffle-in"
          style={{
            transform: 'translateZ(30px)',
            transformStyle: 'preserve-3d',
            filter: 'drop-shadow(0 4px 3px rgba(0, 0, 0, 0.07))',
          }}
        >
          <Card
            accentColor={accentColor}
            className="relative h-full flex flex-col backdrop-blur-lg bg-white/80 dark:bg-zinc-900/80"
          >
            {/* Reflection overlay */}
            <div
              className="card-reflection"
              style={{
                opacity: isGrouped ? 0 : tiltStyles.reflectionOpacity,
                backgroundPosition: tiltStyles.reflectionPosition,
              }}
            ></div>
            {/* Card content for next item */}
            {renderCardContent(
              groupedItem.items[
                (activeCardIndex + 1) % groupedItem.items.length
              ],
            )}
          </Card>
        </div>
      )}
      {/* Sources tooltip */}
      {showTooltip && isGrouped && (
        <div className="absolute bottom-full mb-2 left-1/2 transform -translate-x-1/2 bg-black/90 dark:bg-zinc-800/90 backdrop-blur-md text-white text-xs rounded-lg py-2 px-3 shadow-lg z-50 whitespace-nowrap max-w-xs">
          <div className="font-semibold text-blue-300 mb-1">
            Grouped Sources:
          </div>
          {groupedItem.items.map((item, index) => (
            <div
              key={index}
              className={`text-gray-300 ${activeCardIndex === index ? 'text-blue-300 font-medium' : ''}`}
            >
              {index + 1}. {item.title}
            </div>
          ))}
          <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-t-black dark:border-t-zinc-800"></div>
        </div>
      )}
      {/* Code Examples Modal */}
      {showCodeModal && formattedCodeExamples.length > 0 && (
        <CodeViewerModal
          examples={formattedCodeExamples}
          onClose={() => setShowCodeModal(false)}
        />
      )}
      {/* Delete Confirm Modal */}
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
