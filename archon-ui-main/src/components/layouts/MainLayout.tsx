import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { SideNavigation } from './SideNavigation';
import { KnowledgeChatPanel } from './KnowledgeChatPanel';
import { X } from 'lucide-react';
import { useToast } from '../../contexts/ToastContext';
import { credentialsService } from '../../services/credentialsService';
/**
 * Props for the MainLayout component
 */
interface MainLayoutProps {
  children: React.ReactNode;
}
/**
 * MainLayout - The main layout component for the application
 *
 * This component provides the overall layout structure including:
 * - Side navigation
 * - Main content area
 * - Knowledge chat panel (slidable)
 */
export const MainLayout: React.FC<MainLayoutProps> = ({
  children
}) => {
  // State to track if chat panel is open
  const [isChatOpen, setIsChatOpen] = useState(false);
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [hasShownApiKeyToast, setHasShownApiKeyToast] = useState(false);
  const [backendReady, setBackendReady] = useState(false);

  // Check backend readiness first, then validate credentials
  useEffect(() => {
    if (hasShownApiKeyToast) return; // Don't show multiple times per session
    
    const checkBackendHealth = async (retryCount = 0) => {
      const maxRetries = 5;
      const retryDelay = 1000;
      
      try {
        // Check if backend is responding with a simple health check
        const response = await fetch(`${credentialsService['baseUrl']}/health`, {
          method: 'GET',
          timeout: 5000
        } as any);
        
        if (response.ok) {
          console.log('✅ Backend is ready, checking credentials...');
          setBackendReady(true);
          // Backend is ready, now check credentials
          setTimeout(() => checkOpenAIKey(), 500);
        } else {
          throw new Error(`Backend health check failed: ${response.status}`);
        }
              } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Unknown error';
          console.log(`Backend not ready yet (attempt ${retryCount + 1}/${maxRetries}):`, errorMessage);
        
        // Retry if we haven't exceeded max retries
        if (retryCount < maxRetries) {
          setTimeout(() => {
            checkBackendHealth(retryCount + 1);
          }, retryDelay * Math.pow(1.5, retryCount)); // Exponential backoff
        } else {
          console.warn('Backend not ready after maximum retries - skipping credential check');
          setBackendReady(false);
        }
      }
    };

    const checkOpenAIKey = async (retryCount = 0) => {
      const maxRetries = 3;
      const retryDelay = 1000;
      
      let isBackendReady = false; // Track backend readiness locally to avoid dependency on state
      
      try {
        const credentials = await credentialsService.getCredentialsByCategory('llm_config');
        const openaiKey = credentials.find(cred => cred.key === 'OPENAI_API_KEY');
        
        isBackendReady = true; // If we got here, backend is ready
        
        if (!openaiKey || !openaiKey.value || openaiKey.value.trim() === '') {
          showToast('OpenAI API Key missing! Click here to go to Settings and configure it.', 'warning', 8000);
          setHasShownApiKeyToast(true);
          
          // Add click handler to the document to navigate to settings when toast is clicked
          const handleToastClick = (e: any) => {
            if (e.target.closest('.fixed.top-4.right-4')) {
              navigate('/settings');
              document.removeEventListener('click', handleToastClick);
            }
          };
          document.addEventListener('click', handleToastClick);
        } else {
          console.log('✅ OpenAI API key is configured');
          setHasShownApiKeyToast(true); // Mark as checked to prevent re-checking
        }
      } catch (error) {
        console.error(`Error checking OpenAI API key (attempt ${retryCount + 1}):`, error);
        
        // Retry if we haven't exceeded max retries and backend appears ready
        if (retryCount < maxRetries && isBackendReady) {
          setTimeout(() => {
            checkOpenAIKey(retryCount + 1);
          }, retryDelay * (retryCount + 1)); // Linear backoff for credential check
        } else {
          console.warn('Failed to check OpenAI API key after maximum retries');
          // Don't show error toast for credential check failures - only for missing keys
        }
      }
    };

    // Start the health check process
    setTimeout(() => {
      checkBackendHealth();
    }, 1000); // Wait 1 second for initial app startup
  }, [showToast, navigate, hasShownApiKeyToast]); // Removed backendReady from dependencies to prevent double execution

  return <div className="relative min-h-screen bg-white dark:bg-black overflow-hidden">
      {/* Full-page background grid */}
      <div className="absolute inset-0 neon-grid pointer-events-none z-0"></div>
      {/* Floating Navigation */}
      <div className="fixed left-6 top-1/2 -translate-y-1/2 z-50">
        <SideNavigation />
      </div>
      {/* Main Content Area - no left margin to allow grid to extend full width */}
      <div className="relative flex-1 pl-[100px] z-10">
        <div className="container mx-auto px-8 relative">
          <div className="min-h-screen pt-8 pb-16">{children}</div>
        </div>
      </div>
      {/* Floating Chat Button - Only visible when chat is closed */}
      {!isChatOpen && <button onClick={() => setIsChatOpen(true)} className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full flex items-center justify-center backdrop-blur-md bg-gradient-to-b from-white/10 to-black/30 dark:from-white/10 dark:to-black/30 from-blue-100/80 to-blue-50/60 shadow-[0_0_20px_rgba(59,130,246,0.3)] dark:shadow-[0_0_20px_rgba(59,130,246,0.7)] hover:shadow-[0_0_25px_rgba(59,130,246,0.5)] dark:hover:shadow-[0_0_25px_rgba(59,130,246,0.9)] transition-all duration-300 overflow-hidden border border-blue-200 dark:border-transparent" aria-label="Open Knowledge Assistant">
          <img src="/logo-neon.svg" alt="Archon" className="w-7 h-7" />
        </button>}
      {/* Chat Sidebar - Slides in/out from right */}
      <div className="fixed top-0 right-0 h-full z-40 transition-transform duration-300 ease-in-out transform" style={{
      transform: isChatOpen ? 'translateX(0)' : 'translateX(100%)'
    }}>
        {/* Close button - Only visible when chat is open */}
        {isChatOpen && <button onClick={() => setIsChatOpen(false)} className="absolute -left-14 bottom-6 z-50 w-12 h-12 rounded-full flex items-center justify-center backdrop-blur-md bg-gradient-to-b from-white/10 to-black/30 dark:from-white/10 dark:to-black/30 from-pink-100/80 to-pink-50/60 border border-pink-200 dark:border-pink-500/30 shadow-[0_0_15px_rgba(236,72,153,0.2)] dark:shadow-[0_0_15px_rgba(236,72,153,0.5)] hover:shadow-[0_0_20px_rgba(236,72,153,0.4)] dark:hover:shadow-[0_0_20px_rgba(236,72,153,0.7)] transition-all duration-300" aria-label="Close Knowledge Assistant">
            <X className="w-5 h-5 text-pink-500" />
          </button>}
        {/* Knowledge Chat Panel */}
        <KnowledgeChatPanel data-id="knowledge-chat" />
      </div>
    </div>;
};