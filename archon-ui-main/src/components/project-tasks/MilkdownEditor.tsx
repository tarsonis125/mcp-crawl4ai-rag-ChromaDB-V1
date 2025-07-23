import React, { useEffect, useRef, useState } from 'react';
import { Crepe, CrepeFeature } from '@milkdown/crepe';
import '@milkdown/crepe/theme/common/style.css';
import '@milkdown/crepe/theme/frame.css';
import '@milkdown/crepe/theme/frame-dark.css';
import './MilkdownEditor.css';
import { Save, Undo } from 'lucide-react';

interface MilkdownEditorProps {
  document: {
    id: string;
    title: string;
    content?: any;
    created_at: string;
    updated_at: string;
  };
  onSave: (document: any) => void;
  className?: string;
  isDarkMode?: boolean;
}

export const MilkdownEditor: React.FC<MilkdownEditorProps> = ({
  document: doc,
  onSave,
  className = '',
  isDarkMode = false,
}) => {
  const editorRef = useRef<HTMLDivElement>(null);
  const crepeRef = useRef<Crepe | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [isReverted, setIsReverted] = useState(false);
  const [originalContent, setOriginalContent] = useState<string>('');
  const [currentContent, setCurrentContent] = useState<string>('');

  // Convert document content to markdown string
  const getMarkdownContent = () => {
    if (typeof doc.content === 'string') {
      return doc.content;
    }
    
    if (doc.content && typeof doc.content === 'object') {
      // If content has a markdown field, use it
      if (doc.content.markdown) {
        return doc.content.markdown;
      }
      
      // Otherwise, convert the content object to a readable markdown format
      let markdown = `# ${doc.title}\n\n`;
      
      Object.entries(doc.content).forEach(([key, value]) => {
        const sectionTitle = key.replace(/_/g, ' ').charAt(0).toUpperCase() + key.replace(/_/g, ' ').slice(1);
        markdown += `## ${sectionTitle}\n\n`;
        
        if (Array.isArray(value)) {
          value.forEach(item => {
            markdown += `- ${item}\n`;
          });
          markdown += '\n';
        } else if (typeof value === 'object' && value !== null) {
          if (value.description) {
            markdown += `${value.description}\n\n`;
          } else {
            Object.entries(value).forEach(([subKey, subValue]) => {
              markdown += `**${subKey}:** ${subValue}\n\n`;
            });
          }
        } else {
          markdown += `${value}\n\n`;
        }
      });
      
      return markdown;
    }
    
    return `# ${doc.title}\n\nStart writing...`;
  };

  // Initialize editor
  useEffect(() => {
    if (!editorRef.current || crepeRef.current) return;

    const initialContent = getMarkdownContent();
    setOriginalContent(initialContent);
    setCurrentContent(initialContent);

    // Add theme class to root element
    if (isDarkMode) {
      editorRef.current.classList.add('milkdown-theme-dark');
    }

    const crepe = new Crepe({
      root: editorRef.current,
      defaultValue: initialContent,
      features: {
        [CrepeFeature.HeaderMeta]: true,
        [CrepeFeature.LinkTooltip]: true,
        [CrepeFeature.ImageBlock]: true,
        [CrepeFeature.BlockEdit]: true,
        [CrepeFeature.ListItem]: true,
        [CrepeFeature.CodeBlock]: true,
        [CrepeFeature.Table]: true,
        [CrepeFeature.Toolbar]: true,
      },
    });

    crepe.create().then(() => {
      console.log('Milkdown editor created');
      
      // Set up content change tracking
      const editorElement = editorRef.current?.querySelector('.ProseMirror');
      if (editorElement) {
        // Listen for input events on the editor
        const handleInput = () => {
          // Get current markdown content
          const markdown = crepe.getMarkdown();
          console.log('Editor content changed via input:', markdown.substring(0, 50) + '...');
          setCurrentContent(markdown);
          
          // Compare trimmed content to avoid whitespace issues
          const hasUnsavedChanges = markdown.trim() !== originalContent.trim();
          setHasChanges(hasUnsavedChanges);
          setIsReverted(false);
        };
        
        // Listen to multiple events to catch all changes
        editorElement.addEventListener('input', handleInput);
        editorElement.addEventListener('keyup', handleInput);
        editorElement.addEventListener('paste', handleInput);
        editorElement.addEventListener('cut', handleInput);
        
        // Store the handlers for cleanup
        (editorElement as any)._milkdownHandlers = {
          input: handleInput,
          keyup: handleInput,
          paste: handleInput,
          cut: handleInput
        };
      }
    }).catch((error) => {
      console.error('Failed to create Milkdown editor:', error);
    });

    crepeRef.current = crepe;

    return () => {
      // Clean up event listeners
      const editorElement = editorRef.current?.querySelector('.ProseMirror');
      if (editorElement && (editorElement as any)._milkdownHandlers) {
        const handlers = (editorElement as any)._milkdownHandlers;
        editorElement.removeEventListener('input', handlers.input);
        editorElement.removeEventListener('keyup', handlers.keyup);
        editorElement.removeEventListener('paste', handlers.paste);
        editorElement.removeEventListener('cut', handlers.cut);
        delete (editorElement as any)._milkdownHandlers;
      }
      
      if (crepeRef.current) {
        crepeRef.current.destroy();
        crepeRef.current = null;
      }
    };
  }, [doc.id, originalContent]);

  // Update theme class when isDarkMode changes
  useEffect(() => {
    if (editorRef.current) {
      if (isDarkMode) {
        editorRef.current.classList.add('milkdown-theme-dark');
      } else {
        editorRef.current.classList.remove('milkdown-theme-dark');
      }
    }
  }, [isDarkMode]);

  // Add keyboard shortcut for saving
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        if (hasChanges && !isLoading) {
          handleSave();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [hasChanges, isLoading, currentContent]);

  // Handle manual save
  const handleSave = async () => {
    if (!hasChanges || isLoading) return;
    
    try {
      setIsLoading(true);
      console.log('Saving document with content:', currentContent.substring(0, 100) + '...');
      
      // Create updated document with markdown content stored in content field
      const updatedDocument = {
        ...doc,
        content: {
          markdown: currentContent,
          // Preserve any other content fields
          ...(typeof doc.content === 'object' && doc.content !== null ? doc.content : {})
        },
        updated_at: new Date().toISOString(),
      };
      
      await onSave(updatedDocument);
      
      // Update state after successful save
      setHasChanges(false);
      setIsReverted(false);
      setOriginalContent(currentContent);
      console.log('Document saved successfully');
    } catch (error) {
      console.error('Error saving document:', error);
      // You might want to show an error toast here
    } finally {
      setIsLoading(false);
    }
  };

  // Handle undo changes
  const handleUndo = () => {
    if (crepeRef.current && editorRef.current) {
      // Destroy and recreate editor with original content
      crepeRef.current.destroy();
      
      const crepe = new Crepe({
        root: editorRef.current,
        defaultValue: originalContent,
        features: {
          [CrepeFeature.HeaderMeta]: true,
          [CrepeFeature.LinkTooltip]: true,
          [CrepeFeature.ImageBlock]: true,
          [CrepeFeature.BlockEdit]: true,
          [CrepeFeature.ListItem]: true,
          [CrepeFeature.CodeBlock]: true,
          [CrepeFeature.Table]: true,
          [CrepeFeature.Toolbar]: true,
        },
      });

      crepe.create().then(() => {
        console.log('Milkdown editor reverted to original content');
        
        // Set up content change tracking for the new editor instance
        const editorElement = editorRef.current?.querySelector('.ProseMirror');
        if (editorElement) {
          const handleInput = () => {
            const markdown = crepe.getMarkdown();
            console.log('Editor content changed after undo:', markdown.substring(0, 50) + '...');
            setCurrentContent(markdown);
            const hasUnsavedChanges = markdown.trim() !== originalContent.trim();
            setHasChanges(hasUnsavedChanges);
            setIsReverted(false);
          };
          
          editorElement.addEventListener('input', handleInput);
          editorElement.addEventListener('keyup', handleInput);
          editorElement.addEventListener('paste', handleInput);
          editorElement.addEventListener('cut', handleInput);
          
          (editorElement as any)._milkdownHandlers = {
            input: handleInput,
            keyup: handleInput,
            paste: handleInput,
            cut: handleInput
          };
        }
        
        setCurrentContent(originalContent);
        setHasChanges(false);
        setIsReverted(true);
      }).catch((error) => {
        console.error('Failed to revert Milkdown editor:', error);
      });

      crepeRef.current = crepe;
    }
  };

  return (
    <div className={`milkdown-editor ${className}`}>
      <div className="mb-6 flex items-center justify-between bg-white/50 dark:bg-black/30 backdrop-blur-sm rounded-lg p-4 border border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-3">
          <h3 className="text-xl font-semibold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            {doc.title}
          </h3>
          <div className="flex items-center gap-2">
            {isLoading ? (
              <span className="text-sm text-blue-600 dark:text-blue-400 flex items-center gap-2">
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                Saving...
              </span>
            ) : isReverted ? (
              <span className="text-sm text-purple-600 dark:text-purple-400 flex items-center gap-2">
                <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                Reverted
              </span>
            ) : hasChanges ? (
              <span className="text-sm text-orange-600 dark:text-orange-400 flex items-center gap-2">
                <div className="w-2 h-2 bg-orange-500 rounded-full animate-pulse"></div>
                Unsaved changes
              </span>
            ) : (
              <span className="text-sm text-green-600 dark:text-green-400 flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                All changes saved
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {hasChanges && (
            <button
              onClick={handleUndo}
              disabled={isLoading}
              className="px-4 py-2 bg-gray-500/20 hover:bg-gray-500/30 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 border border-gray-300 dark:border-gray-600"
            >
              <Undo className="w-4 h-4" />
              Undo
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={isLoading || !hasChanges}
            className={`
              px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 
              flex items-center gap-2 border
              ${hasChanges 
                ? 'bg-blue-500 hover:bg-blue-600 text-white border-blue-600 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 save-button-pulse' 
                : 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-600 border-gray-300 dark:border-gray-700 cursor-not-allowed'
              }
              disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-none
            `}
          >
            <Save className="w-4 h-4" />
            {isLoading ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
      
      <div 
        ref={editorRef} 
        className={`prose prose-lg max-w-none milkdown-crepe-editor ${isDarkMode ? 'prose-invert' : ''}`}
        style={{ minHeight: '400px' }}
      />
    </div>
  );
};