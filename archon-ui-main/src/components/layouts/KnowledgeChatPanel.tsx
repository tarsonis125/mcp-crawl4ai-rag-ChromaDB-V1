import React, { useEffect, useState, useRef, Component } from 'react';
import { Send, User } from 'lucide-react';
import { ArchonLoadingSpinner, EdgeLitEffect } from '../animations/Animations';
/**
 * Message interface representing chat messages in the knowledge assistant
 */
interface Message {
  id: string;
  content: string;
  sender: 'user' | 'ai';
  timestamp: Date;
  isLoading?: boolean;
}
/**
 * Props for the KnowledgeChatPanel component
 */
interface KnowledgeChatPanelProps {
  'data-id'?: string;
}
/**
 * KnowledgeChatPanel - A chat interface for the knowledge assistant
 *
 * This component provides a resizable chat panel with message history,
 * loading states, and input functionality.
 */
export const KnowledgeChatPanel: React.FC<KnowledgeChatPanelProps> = props => {
  // Initial sample messages
  const [messages, setMessages] = useState<Message[]>([{
    id: '1',
    content: 'Hello! How can I help you with your knowledge base today?',
    sender: 'ai',
    timestamp: new Date(Date.now() - 60000 * 10)
  }, {
    id: '2',
    content: 'I need to find documents related to React component patterns.',
    sender: 'user',
    timestamp: new Date(Date.now() - 60000 * 8)
  }, {
    id: '3',
    content: 'I found 3 documents about React component patterns. The most relevant is "React Component Design Patterns" which covers best practices for scalable applications.',
    sender: 'ai',
    timestamp: new Date(Date.now() - 60000 * 7)
  }]);
  // State for input field, panel width, loading state, and dragging state
  const [inputValue, setInputValue] = useState('');
  const [width, setWidth] = useState(320); // Default width
  const [isLoading, setIsLoading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  // Refs for DOM elements
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const dragHandleRef = useRef<HTMLDivElement>(null);
  const chatPanelRef = useRef<HTMLDivElement>(null);
  /**
   * Handle resizing of the chat panel via drag
   */
  useEffect(() => {
    // Handler for mouse movement during drag
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging && chatPanelRef.current) {
        const containerRect = chatPanelRef.current.parentElement?.getBoundingClientRect();
        if (containerRect) {
          // Calculate new width based on mouse position (from right edge of screen)
          const newWidth = window.innerWidth - e.clientX;
          // Set min and max width constraints
          if (newWidth >= 280 && newWidth <= 600) {
            setWidth(newWidth);
          }
        }
      }
    };
    // Handler for mouse up to end dragging
    const handleMouseUp = () => {
      setIsDragging(false);
      document.body.style.cursor = 'default';
      document.body.style.userSelect = 'auto';
    };
    // Add event listeners when dragging
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'ew-resize';
      document.body.style.userSelect = 'none'; // Prevent text selection while dragging
    }
    // Clean up event listeners
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);
  /**
   * Handler for starting the drag operation
   */
  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };
  /**
   * Auto-scroll to the bottom when messages change
   */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: 'smooth'
    });
  }, [messages]);
  /**
   * Handle sending a new message and simulating AI response
   */
  const handleSendMessage = () => {
    if (inputValue.trim()) {
      // Add user message
      const newMessage: Message = {
        id: Date.now().toString(),
        content: inputValue,
        sender: 'user',
        timestamp: new Date()
      };
      setMessages([...messages, newMessage]);
      setInputValue('');
      setIsLoading(true);
      // Add a loading message
      const loadingMessageId = (Date.now() + 1).toString();
      setMessages(prev => [...prev, {
        id: loadingMessageId,
        content: '',
        sender: 'ai',
        timestamp: new Date(),
        isLoading: true
      }]);
      // Simulate AI response with 2 second delay
      setTimeout(() => {
        setIsLoading(false);
        setMessages(prev => prev.filter(msg => msg.id !== loadingMessageId).concat({
          id: (Date.now() + 2).toString(),
          content: "I'm analyzing your request. Let me find the most relevant information for you.",
          sender: 'ai',
          timestamp: new Date()
        }));
      }, 2000);
    }
  };
  /**
   * Format timestamp for display in messages
   */
  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit'
    });
  };
  return <div ref={chatPanelRef} className="h-full flex flex-col relative" style={{
    width: `${width}px`
  }} data-id={props['data-id']}>
      {/* Drag handle for resizing */}
      <div ref={dragHandleRef} className={`absolute left-0 top-0 w-1.5 h-full cursor-ew-resize z-20 ${isDragging ? 'bg-blue-500/50' : 'bg-transparent hover:bg-blue-500/30'} transition-colors duration-200`} onMouseDown={handleDragStart} />
      {/* Main panel with glassmorphism */}
      <div className="h-full flex flex-col relative backdrop-blur-md bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border-l border-blue-200 dark:border-blue-500/30">
        {/* Edgelit glow effect */}
        <EdgeLitEffect color="blue" />
        {/* Header gradient background */}
        <div className="absolute top-0 left-0 right-0 h-16 bg-gradient-to-b from-blue-100 to-white dark:from-blue-500/20 dark:to-blue-500/5 rounded-t-md pointer-events-none"></div>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-zinc-800/80">
          <div className="flex items-center">
            {/* Archon Logo - No animation in header */}
            <div className="relative w-8 h-8 mr-3 flex items-center justify-center">
              <img src="/logo-neon.svg" alt="Archon" className="w-6 h-6 z-10 relative" />
            </div>
            <h2 className="text-gray-800 dark:text-white font-medium z-10 relative">
              Knowledge Assistant
            </h2>
          </div>
        </div>
        {/* Messages area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50/50 dark:bg-transparent">
          {messages.map(message => <div key={message.id} className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
              {message.isLoading ? <div className="max-w-[80%] mr-auto flex items-center justify-center py-4">
                  {/* Loading spinner animation */}
                  <ArchonLoadingSpinner size="md" />
                </div> : <div className={`
                    max-w-[80%] rounded-lg p-3 
                    ${message.sender === 'user' ? 'bg-purple-100/80 dark:bg-purple-500/20 border border-purple-200 dark:border-purple-500/30 ml-auto' : 'bg-blue-100/80 dark:bg-blue-500/20 border border-blue-200 dark:border-blue-500/30 mr-auto'}
                  `}>
                  <div className="flex items-center mb-1">
                    {message.sender === 'ai' ? <div className="w-4 h-4 mr-1 flex items-center justify-center">
                        <img src="/logo-neon.svg" alt="Archon" className="w-full h-full" />
                      </div> : <User className="w-4 h-4 text-purple-500 mr-1" />}
                    <span className="text-xs text-gray-500 dark:text-zinc-400">
                      {formatTime(message.timestamp)}
                    </span>
                  </div>
                  <p className="text-gray-800 dark:text-white text-sm">
                    {message.content}
                  </p>
                </div>}
            </div>)}
          <div ref={messagesEndRef} />
        </div>
        {/* Input area */}
        <div className="p-4 border-t border-gray-200 dark:border-zinc-800/80 bg-white/60 dark:bg-transparent">
          <div className="flex items-center gap-2">
            {/* Text input field */}
            <div className="flex-1 backdrop-blur-md bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30 border border-gray-200 dark:border-zinc-800/80 rounded-md px-3 py-2 focus-within:border-blue-500 focus-within:shadow-[0_0_15px_rgba(59,130,246,0.5)] transition-all duration-200">
              <input type="text" value={inputValue} onChange={e => setInputValue(e.target.value)} placeholder="Ask a question..." className="w-full bg-transparent text-gray-800 dark:text-white placeholder:text-gray-500 dark:placeholder:text-zinc-600 focus:outline-none" onKeyDown={e => {
              if (e.key === 'Enter') handleSendMessage();
            }} />
            </div>
            {/* Send button */}
            <button onClick={handleSendMessage} className="relative flex items-center justify-center p-2 rounded-md overflow-hidden group" disabled={isLoading}>
              {/* Glass background */}
              <div className="absolute inset-0 backdrop-blur-md bg-gradient-to-b from-blue-100/80 to-blue-50/60 dark:from-white/5 dark:to-black/20 rounded-md"></div>
              {/* Neon border glow */}
              <div className={`absolute inset-0 rounded-md border-2 border-blue-400 ${isLoading ? 'opacity-30' : 'opacity-60 group-hover:opacity-100'} shadow-[0_0_10px_rgba(59,130,246,0.3),inset_0_0_6px_rgba(59,130,246,0.2)] dark:shadow-[0_0_10px_rgba(59,130,246,0.6),inset_0_0_6px_rgba(59,130,246,0.4)] transition-all duration-300`}></div>
              {/* Inner glow effect */}
              <div className={`absolute inset-[1px] rounded-sm bg-blue-100/30 dark:bg-blue-500/10 ${isLoading ? 'opacity-20' : 'opacity-30 group-hover:opacity-40'} transition-all duration-200`}></div>
              {/* Send icon with neon glow */}
              <Send className={`w-4 h-4 text-blue-500 dark:text-blue-400 relative z-10 ${isLoading ? 'opacity-50' : 'opacity-90 group-hover:opacity-100'} drop-shadow-[0_0_3px_rgba(59,130,246,0.5)] dark:drop-shadow-[0_0_3px_rgba(59,130,246,0.8)] transition-all duration-200`} />
              {/* Shine effect */}
              <div className="absolute top-0 left-0 w-full h-[1px] bg-white/40 rounded-t-md"></div>
            </button>
          </div>
        </div>
      </div>
    </div>;
};