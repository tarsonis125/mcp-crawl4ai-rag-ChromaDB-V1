import { useState } from 'react';
import { Link as LinkIcon, Upload, Trash2, RefreshCw, X, Code, FileText, Brain, BoxIcon } from 'lucide-react';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { KnowledgeItem } from '../../services/knowledgeBaseService';
import { useCardTilt } from '../../hooks/useCardTilt';
import { CodeViewerModal, CodeExample } from '../code/CodeViewerModal';
import '../../styles/card-animations.css';

// Helper function to guess language from title
const guessLanguageFromTitle = (title: string = ''): string => {
  const titleLower = title.toLowerCase();
  if (titleLower.includes('javascript') || titleLower.includes('js')) return 'javascript';
  if (titleLower.includes('typescript') || titleLower.includes('ts')) return 'typescript';
  if (titleLower.includes('react')) return 'jsx';
  if (titleLower.includes('html')) return 'html';
  if (titleLower.includes('css')) return 'css';
  if (titleLower.includes('python')) return 'python';
  if (titleLower.includes('java')) return 'java';
  return 'javascript'; // Default
};

// Tags display component
interface TagsDisplayProps {
  tags: string[];
}

const TagsDisplay = ({ tags }: TagsDisplayProps) => {
  const [showTooltip, setShowTooltip] = useState(false);
  
  if (!tags || tags.length === 0) return null;
  
  const visibleTags = tags.slice(0, 4);
  const remainingTags = tags.slice(4);
  const hasMoreTags = remainingTags.length > 0;
  
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
  );
};

// Delete confirmation modal component
interface DeleteConfirmModalProps {
  onConfirm: () => void;
  onCancel: () => void;
  title: string;
  message: string;
}

const DeleteConfirmModal = ({
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
  );
};

interface KnowledgeItemCardProps {
  item: KnowledgeItem;
  onDelete: (sourceId: string) => void;
}

export const KnowledgeItemCard = ({
  item,
  onDelete
}: KnowledgeItemCardProps) => {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showCodeModal, setShowCodeModal] = useState(false);
  const [showCodeTooltip, setShowCodeTooltip] = useState(false);
  const [isRemoving, setIsRemoving] = useState(false);

  const statusColorMap = {
    active: 'green',
    processing: 'blue',
    error: 'pink'
  };
  const accentColor = item.metadata.source_type === 'url' ? 'blue' : 'pink';
  
  // Get the type icon
  const TypeIcon = item.metadata.knowledge_type === 'technical' ? BoxIcon : Brain;
  const typeIconColor = item.metadata.knowledge_type === 'technical' ? 'text-blue-500' : 'text-purple-500';

  // Use the tilt effect hook
  const { cardRef, tiltStyles, handlers } = useCardTilt({
    max: 10,
    scale: 1.02,
    perspective: 1200,
  });

  const handleDelete = () => {
    setIsRemoving(true);
    // Delay the actual deletion to allow for the animation
    setTimeout(() => {
      onDelete(item.source_id);
      setShowDeleteConfirm(false);
    }, 500);
  };

  // Get frequency display
  const getFrequencyDisplay = () => {
    const frequency = item.metadata.update_frequency;
    if (!frequency || frequency === 0) {
      return { icon: <X className="w-3 h-3" />, text: 'Never', color: 'text-gray-500 dark:text-zinc-500' };
    } else if (frequency === 1) {
      return { icon: <RefreshCw className="w-3 h-3" />, text: 'Daily', color: 'text-green-500' };
    } else if (frequency === 7) {
      return { icon: <RefreshCw className="w-3 h-3" />, text: 'Weekly', color: 'text-blue-500' };
    } else if (frequency === 30) {
      return { icon: <RefreshCw className="w-3 h-3" />, text: 'Monthly', color: 'text-purple-500' };
    } else {
      return { icon: <RefreshCw className="w-3 h-3" />, text: `Every ${frequency} days`, color: 'text-gray-500 dark:text-zinc-500' };
    }
  };

  const frequencyDisplay = getFrequencyDisplay();

  // Get code examples count
  const codeExamplesCount = item.code_examples?.length || 0;

  // Format code examples for the modal
  const codeExamples: CodeExample[] = 
    item.code_examples?.map((example: any, index: number) => ({
      id: example.id || `${item.id}-example-${index}`,
      title: example.metadata?.example_name || example.metadata?.title || example.summary?.split('\n')[0] || 'Code Example',
      description: example.summary || 'No description available',
      language: example.metadata?.language || guessLanguageFromTitle(example.metadata?.title || ''),
      code: example.content || example.metadata?.code || '// Code example not available',
      tags: example.metadata?.tags || [],
    })) || [];

  return (
    <div
      ref={cardRef}
      className={`card-3d relative h-full ${isRemoving ? 'card-removing' : ''}`}
      style={{
        transform: tiltStyles.transform,
        transition: tiltStyles.transition,
      }}
      {...(showCodeModal ? {} : handlers)}
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
            {item.metadata.source_type === 'url' ? (
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
                  e.stopPropagation();
                  setShowDeleteConfirm(true);
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
            {item.metadata.description || 'No description available'}
          </p>
          
          {/* Tags section - flexible height with flex-1 */}
          <div className="flex-1 flex flex-col card-3d-layer-2 min-h-[4rem]">
            <TagsDisplay tags={item.metadata.tags || []} />
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
                Updated: {new Date(item.updated_at).toLocaleDateString()}
              </span>
            </div>
            
            {/* Right side - code examples, page count and status inline */}
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
                  {/* Code Examples Tooltip */}
                  {showCodeTooltip && (
                    <div className="absolute bottom-full mb-2 left-1/2 transform -translate-x-1/2 bg-black dark:bg-zinc-800 text-white text-xs rounded-lg py-2 px-3 shadow-lg z-50 max-w-xs">
                      <div className="font-semibold text-pink-300 mb-1">
                        Code Examples:
                      </div>
                      <div className="max-h-48 overflow-y-auto">
                        {codeExamples.map((example, index) => (
                          <div key={index} className="mb-2 last:mb-0">
                            <div className="text-pink-200 font-medium">
                              {example.title}
                            </div>
                            <div className="text-gray-300 text-xs">
                              {example.description}
                            </div>
                          </div>
                        ))}
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
                    {Math.ceil(
                      (item.metadata.word_count || 0) / 250,
                    ).toLocaleString()}
                  </span>
                </div>
                {/* Tooltip */}
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-200 z-50">
                  <div className="bg-black dark:bg-zinc-800 text-white text-xs px-3 py-2 rounded-lg shadow-lg whitespace-nowrap">
                    <div className="font-medium mb-1">
                      {item.metadata.word_count?.toLocaleString() || 0} words
                    </div>
                    <div className="text-gray-300 space-y-0.5">
                      <div>
                        ={' '}
                        {Math.ceil(
                          (item.metadata.word_count || 0) / 250,
                        ).toLocaleString()}{' '}
                        pages
                      </div>
                      <div>
                        = {((item.metadata.word_count || 0) / 80000).toFixed(1)}{' '}
                        average novels
                      </div>
                    </div>
                    <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-t-black dark:border-t-zinc-800"></div>
                  </div>
                </div>
              </div>
              
              <Badge
                color={statusColorMap[item.metadata.status || 'active'] as any}
                className="card-3d-layer-2"
              >
                {(item.metadata.status || 'active').charAt(0).toUpperCase() +
                  (item.metadata.status || 'active').slice(1)}
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
  );
}; 