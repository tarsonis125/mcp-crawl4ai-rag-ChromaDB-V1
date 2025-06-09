import React, { useEffect, useState } from 'react';
import { useCreateBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/mantine";
import "@blocknote/core/fonts/inter.css";
import "@blocknote/mantine/style.css";
import { Block, PartialBlock } from "@blocknote/core";

// Define types locally to match DocsTab exactly
interface ArchonBlock {
  id: string;
  type: 'paragraph' | 'heading_1' | 'heading_2' | 'heading_3' | 'bulleted_list' | 'numbered_list' | 'to_do' | 'callout' | 'divider' | 'quote';
  content: any;
  properties?: {
    title?: string;
    color?: string;
    checked?: boolean;
    text?: string;
  };
}

interface ArchonDocument {
  id: string;
  title: string;
  blocks: ArchonBlock[];
  created_at: string;
  updated_at: string;
}

interface BlockNoteEditorProps {
  document: ArchonDocument | any; // Support both formats
  onSave: (document: ArchonDocument) => void;
  className?: string;
  isDarkMode?: boolean;
}

// Convert our ArchonBlock format to BlockNote format
const convertArchonToBlockNote = (archonBlocks: ArchonBlock[]): PartialBlock[] => {
  if (!archonBlocks || archonBlocks.length === 0) {
    return [];
  }
  
  return archonBlocks.map((block): PartialBlock => {
    // Get text content from various possible locations
    const getText = () => {
      if (typeof block.content === 'string') return block.content;
      if (block.properties?.text) return block.properties.text;
      if (block.properties?.title) return block.properties.title;
      if (Array.isArray(block.content)) return block.content.join('\n');
      return '';
    };

    switch (block.type) {
      case 'paragraph':
        return {
          id: block.id,
          type: 'paragraph',
          content: getText(),
        };
      
      case 'heading_1':
        return {
          id: block.id,
          type: 'heading',
          props: { level: 1 },
          content: getText(),
        };
      
      case 'heading_2':
        return {
          id: block.id,
          type: 'heading',
          props: { level: 2 },
          content: getText(),
        };
      
      case 'heading_3':
        return {
          id: block.id,
          type: 'heading',
          props: { level: 3 },
          content: getText(),
        };
      
      case 'bulleted_list':
        return {
          id: block.id,
          type: 'bulletListItem',
          content: getText(),
        };
      
      case 'numbered_list':
        return {
          id: block.id,
          type: 'numberedListItem',
          content: getText(),
        };
      
      case 'to_do':
        return {
          id: block.id,
          type: 'checkListItem',
          props: { checked: block.properties?.checked || false },
          content: getText(),
        };
      
      case 'quote':
        return {
          id: block.id,
          type: 'quote',
          content: getText(),
        };
      
      case 'divider':
        return {
          id: block.id,
          type: 'paragraph',
          content: '---',
        };
      
      default:
        return {
          id: block.id,
          type: 'paragraph',
          content: getText(),
        };
    }
  });
};

// Convert BlockNote format back to our ArchonBlock format
const convertBlockNoteToArchon = (blockNoteBlocks: Block[]): ArchonBlock[] => {
  return blockNoteBlocks.map((block): ArchonBlock => {
    // Extract text content safely
    const extractText = (content: any): string => {
      if (typeof content === 'string') {
        return content;
      }
      if (Array.isArray(content)) {
        return content
          .map(item => {
            if (typeof item === 'string') return item;
            if (item && typeof item === 'object' && 'text' in item) return item.text;
            if (item && typeof item === 'object' && 'type' in item && item.type === 'text' && 'text' in item) return item.text;
            return '';
          })
          .join('');
      }
      return '';
    };

    const textContent = extractText(block.content);

    const baseBlock = {
      id: block.id,
      content: textContent,
      properties: {
        text: textContent,
      },
    };

    switch (block.type) {
      case 'paragraph':
        return { ...baseBlock, type: 'paragraph' as const };
      
      case 'heading':
        const level = (block.props as any)?.level || 1;
        const headingType: 'heading_1' | 'heading_2' | 'heading_3' = 
          level === 1 ? 'heading_1' : level === 2 ? 'heading_2' : 'heading_3';
        return { 
          ...baseBlock, 
          type: headingType
        };
      
      case 'bulletListItem':
        return { ...baseBlock, type: 'bulleted_list' as const };
      
      case 'numberedListItem':
        return { ...baseBlock, type: 'numbered_list' as const };
      
      case 'checkListItem':
        return { 
          ...baseBlock, 
          type: 'to_do' as const,
          properties: {
            ...baseBlock.properties,
            checked: (block.props as any)?.checked || false,
          }
        };
      
      case 'quote':
        return { ...baseBlock, type: 'quote' as const };
      
      default:
        return { ...baseBlock, type: 'paragraph' as const };
    }
  });
};

// Convert Archon MCP document format to our block format
const convertMCPDocumentToBlocks = (mcpDocument: any): ArchonBlock[] => {
  if (!mcpDocument.content) {
    return [];
  }
  
  const blocks: ArchonBlock[] = [];
  let blockId = 1;
  
  // Convert the content object to blocks
  const content = mcpDocument.content;
  
  // Add document title as heading
  if (mcpDocument.title) {
    blocks.push({
      id: `block-${blockId++}`,
      type: 'heading_1',
      content: mcpDocument.title,
      properties: { title: mcpDocument.title }
    });
  }
  
  // Handle project overview
  if (content.project_overview) {
    blocks.push({
      id: `block-${blockId++}`,
      type: 'heading_2',
      content: 'Project Overview',
      properties: { title: 'Project Overview' }
    });
    
    if (content.project_overview.description) {
      blocks.push({
        id: `block-${blockId++}`,
        type: 'paragraph',
        content: content.project_overview.description,
        properties: { text: content.project_overview.description }
      });
    }
    
    if (content.project_overview.target_completion) {
      blocks.push({
        id: `block-${blockId++}`,
        type: 'paragraph',
        content: `Target Completion: ${content.project_overview.target_completion}`,
        properties: { text: `Target Completion: ${content.project_overview.target_completion}` }
      });
    }
  }
  
  // Handle goals
  if (content.goals && Array.isArray(content.goals)) {
    blocks.push({
      id: `block-${blockId++}`,
      type: 'heading_2',
      content: 'Goals',
      properties: { title: 'Goals' }
    });
    content.goals.forEach((goal: string) => {
      blocks.push({
        id: `block-${blockId++}`,
        type: 'bulleted_list',
        content: goal,
        properties: { text: goal }
      });
    });
  }
  
  // Handle scope
  if (content.scope) {
    blocks.push({
      id: `block-${blockId++}`,
      type: 'heading_2',
      content: 'Scope',
      properties: { title: 'Scope' }
    });
    Object.entries(content.scope).forEach(([key, value]) => {
      blocks.push({
        id: `block-${blockId++}`,
        type: 'paragraph',
        content: `**${key}:** ${value}`,
        properties: { text: `**${key}:** ${value}` }
      });
    });
  }
  
  // Handle architecture
  if (content.architecture) {
    blocks.push({
      id: `block-${blockId++}`,
      type: 'heading_2',
      content: 'Architecture',
      properties: { title: 'Architecture' }
    });
    Object.entries(content.architecture).forEach(([key, value]) => {
      blocks.push({
        id: `block-${blockId++}`,
        type: 'heading_3',
        content: key.charAt(0).toUpperCase() + key.slice(1),
        properties: { title: key.charAt(0).toUpperCase() + key.slice(1) }
      });
      if (Array.isArray(value)) {
        value.forEach((item: string) => {
          blocks.push({
            id: `block-${blockId++}`,
            type: 'bulleted_list',
            content: item,
            properties: { text: item }
          });
        });
      } else if (typeof value === 'string') {
        blocks.push({
          id: `block-${blockId++}`,
          type: 'paragraph',
          content: value,
          properties: { text: value }
        });
      }
    });
  }
  
  // Handle tech packages
  if (content.tech_packages) {
    blocks.push({
      id: `block-${blockId++}`,
      type: 'heading_2',
      content: 'Technology Stack',
      properties: { title: 'Technology Stack' }
    });
    Object.entries(content.tech_packages).forEach(([key, value]) => {
      blocks.push({
        id: `block-${blockId++}`,
        type: 'heading_3',
        content: key.replace(/_/g, ' ').charAt(0).toUpperCase() + key.replace(/_/g, ' ').slice(1),
        properties: { title: key.replace(/_/g, ' ').charAt(0).toUpperCase() + key.replace(/_/g, ' ').slice(1) }
      });
      if (Array.isArray(value)) {
        value.forEach((item: string) => {
          blocks.push({
            id: `block-${blockId++}`,
            type: 'bulleted_list',
            content: item,
            properties: { text: item }
          });
        });
      }
    });
  }
  
  // Handle UI/UX requirements
  if (content.ui_ux_requirements) {
    blocks.push({
      id: `block-${blockId++}`,
      type: 'heading_2',
      content: 'UI/UX Requirements',
      properties: { title: 'UI/UX Requirements' }
    });
    Object.entries(content.ui_ux_requirements).forEach(([key, value]) => {
      blocks.push({
        id: `block-${blockId++}`,
        type: 'heading_3',
        content: key.replace(/_/g, ' ').charAt(0).toUpperCase() + key.replace(/_/g, ' ').slice(1),
        properties: { title: key.replace(/_/g, ' ').charAt(0).toUpperCase() + key.replace(/_/g, ' ').slice(1) }
      });
      if (Array.isArray(value)) {
        value.forEach((item: string) => {
          blocks.push({
            id: `block-${blockId++}`,
            type: 'bulleted_list',
            content: item,
            properties: { text: item }
          });
        });
              } else if (typeof value === 'object' && value !== null) {
          Object.entries(value).forEach(([subKey, subValue]) => {
          blocks.push({
            id: `block-${blockId++}`,
            type: 'paragraph',
            content: `**${subKey}:** ${subValue}`,
            properties: { text: `**${subKey}:** ${subValue}` }
          });
        });
      }
    });
  }
  
  return blocks;
};

export const BlockNoteEditor: React.FC<BlockNoteEditorProps> = ({
  document,
  onSave,
  className = '',
  isDarkMode = false,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  
  // Handle different document formats
  const normalizedDocument: ArchonDocument = React.useMemo(() => {
    // If it's already in the right format AND has actual blocks content
    if (document.blocks && Array.isArray(document.blocks) && document.blocks.length > 0) {
      return document as ArchonDocument;
    }
    
    // If it's from Archon MCP with content object OR has empty blocks but content exists
    if (document.content && typeof document.content === 'object') {
      const convertedBlocks = convertMCPDocumentToBlocks(document);
      return {
        id: document.id || `doc-${Date.now()}`,
        title: document.title || 'Untitled Document',
        blocks: convertedBlocks,
        created_at: document.created_at || new Date().toISOString(),
        updated_at: document.updated_at || new Date().toISOString(),
      };
    }
    
    // Fallback for empty document
    return {
      id: document.id || `doc-${Date.now()}`,
      title: document.title || 'Untitled Document',
      blocks: [],
      created_at: document.created_at || new Date().toISOString(),
      updated_at: document.updated_at || new Date().toISOString(),
    };
  }, [document]);
  
  // Convert our document format to BlockNote format for initial content
  const initialContent = convertArchonToBlockNote(normalizedDocument.blocks);
  
  // Define dark and light themes
  const archonTheme = {
    light: {
      colors: {
        editor: {
          text: "#1f2937",
          background: "#ffffff",
        },
        menu: {
          text: "#374151",
          background: "#f9fafb",
        },
        tooltip: {
          text: "#111827",
          background: "#f3f4f6",
        },
        hovered: {
          text: "#1f2937",
          background: "#f3f4f6",
        },
        selected: {
          text: "#ffffff",
          background: "#3b82f6",
        },
        disabled: {
          text: "#9ca3af",
          background: "#f9fafb",
        },
        shadow: "#e5e7eb",
        border: "#e5e7eb",
        sideMenu: "#9ca3af",
        highlights: {
          gray: { text: "#6b7280", background: "#f3f4f6" },
          blue: { text: "#1d4ed8", background: "#dbeafe" },
          purple: { text: "#7c3aed", background: "#ede9fe" },
          pink: { text: "#be185d", background: "#fce7f3" },
        },
      },
      borderRadius: 8,
      fontFamily: "Inter, system-ui, sans-serif",
    },
    dark: {
      colors: {
        editor: {
          text: "#f9fafb",
          background: "#111827",
        },
        menu: {
          text: "#e5e7eb",
          background: "#1f2937",
        },
        tooltip: {
          text: "#f3f4f6",
          background: "#374151",
        },
        hovered: {
          text: "#f9fafb",
          background: "#374151",
        },
        selected: {
          text: "#ffffff",
          background: "#3b82f6",
        },
        disabled: {
          text: "#6b7280",
          background: "#1f2937",
        },
        shadow: "#000000",
        border: "#374151",
        sideMenu: "#6b7280",
        highlights: {
          gray: { text: "#9ca3af", background: "#374151" },
          blue: { text: "#60a5fa", background: "#1e3a8a" },
          purple: { text: "#a78bfa", background: "#5b21b6" },
          pink: { text: "#f472b6", background: "#9d174d" },
        },
      },
      borderRadius: 8,
      fontFamily: "Inter, system-ui, sans-serif",
    },
  };
  
  // Create BlockNote editor with initial content and theme
  const editor = useCreateBlockNote({
    initialContent: initialContent.length > 0 ? initialContent : undefined,
  });

  // Update editor content when document changes
  useEffect(() => {
    const newContent = convertArchonToBlockNote(normalizedDocument.blocks);
    if (newContent.length > 0) {
      editor.replaceBlocks(editor.document, newContent);
    } else {
      // Clear editor for empty documents
      editor.replaceBlocks(editor.document, []);
    }
  }, [normalizedDocument.id, normalizedDocument.blocks, editor]);

  // Handle manual save
  const handleSave = async () => {
    try {
      setIsLoading(true);
      
      // Get current blocks from editor
      const currentBlocks = editor.document;
      
      // Convert back to our format
      const archonBlocks = convertBlockNoteToArchon(currentBlocks);
      
      // Create updated document
      const updatedDocument: ArchonDocument = {
        ...normalizedDocument,
        blocks: archonBlocks,
        updated_at: new Date().toISOString(),
      };
      
      // Save the document
      await onSave(updatedDocument);
      setHasChanges(false); // Reset changes after successful save
    } catch (error) {
      console.error('Error saving document:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Set up change detection (no auto-save)
  useEffect(() => {
    const handleContentChange = () => {
      setHasChanges(true);
    };

    // Listen for editor changes
    const unsubscribe = editor.onChange(handleContentChange);

    // Cleanup function
    return () => {
      if (unsubscribe) {
        unsubscribe();
      }
    };
  }, [editor]);

  return (
    <div className={`blocknote-editor ${className}`}>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold">{normalizedDocument.title}</h3>
          {isLoading ? (
            <div className="text-sm text-muted-foreground flex items-center gap-1">
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
              Saving...
            </div>
          ) : hasChanges ? (
            <div className="text-sm text-orange-500 flex items-center gap-1">
              <div className="w-2 h-2 bg-orange-500 rounded-full"></div>
              Changes made
            </div>
          ) : (
            <div className="text-sm text-green-500 flex items-center gap-1">
              <div className="w-2 h-2 bg-green-500 rounded-full"></div>
              Saved
            </div>
          )}
        </div>
        {hasChanges && (
          <button
            onClick={handleSave}
            disabled={isLoading}
            className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Save
          </button>
        )}
      </div>
      
      <div className="prose max-w-none">
        <BlockNoteView 
          editor={editor}
          theme={isDarkMode ? archonTheme.dark : archonTheme.light}
        />
      </div>
    </div>
  );
}; 