import { useEffect, useState, useRef } from 'react';
import { Search, Grid, Plus, Upload, Link as LinkIcon, Brain, Filter, BoxIcon, List, BookOpen } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Badge } from '../components/ui/Badge';
import { GlassCrawlDepthSelector } from '../components/ui/GlassCrawlDepthSelector';
import { useStaggeredEntrance } from '../hooks/useStaggeredEntrance';
import { useToast } from '../contexts/ToastContext';
import { knowledgeBaseService, KnowledgeItem, KnowledgeItemMetadata } from '../services/knowledgeBaseService';
import { knowledgeSocketIO } from '../services/socketIOService';
import { CrawlingProgressCard } from '../components/knowledge-base/CrawlingProgressCard';
import { CrawlProgressData, crawlProgressService } from '../services/crawlProgressService';
import { WebSocketState } from '../services/socketIOService';
import { KnowledgeTable } from '../components/knowledge-base/KnowledgeTable';
import { KnowledgeItemCard } from '../components/knowledge-base/KnowledgeItemCard';
import { GroupedKnowledgeItemCard } from '../components/knowledge-base/GroupedKnowledgeItemCard';
import { KnowledgeGridSkeleton, KnowledgeTableSkeleton } from '../components/knowledge-base/KnowledgeItemSkeleton';

const extractDomain = (url: string): string => {
  try {
    const urlObj = new URL(url);
    const hostname = urlObj.hostname;
    
    // Remove 'www.' prefix if present
    const withoutWww = hostname.startsWith('www.') ? hostname.slice(4) : hostname;
    
    // For domains with subdomains, extract the main domain (last 2 parts)
    const parts = withoutWww.split('.');
    if (parts.length > 2) {
      // Return the main domain (last 2 parts: domain.tld)
      return parts.slice(-2).join('.');
    }
    
    return withoutWww;
  } catch {
    return url; // Return original if URL parsing fails
  }
};

interface GroupedKnowledgeItem {
  id: string;
  title: string;
  domain: string;
  items: KnowledgeItem[];
  metadata: KnowledgeItemMetadata;
  created_at: string;
  updated_at: string;
}

const groupItemsByDomain = (items: KnowledgeItem[]): GroupedKnowledgeItem[] => {
  const groups = new Map<string, KnowledgeItem[]>();
  
  // Group items by domain
  items.forEach(item => {
    // Only group URL-based items, not file uploads
    if (item.metadata.source_type === 'url') {
      const domain = extractDomain(item.url);
      const existing = groups.get(domain) || [];
      groups.set(domain, [...existing, item]);
    } else {
      // File uploads remain ungrouped
      groups.set(`file_${item.id}`, [item]);
    }
  });
  
  // Convert groups to GroupedKnowledgeItem objects
  return Array.from(groups.entries()).map(([domain, groupItems]) => {
    const firstItem = groupItems[0];
    const isFileGroup = domain.startsWith('file_');
    
    // Find the latest update timestamp and convert it properly to ISO string
    const latestTimestamp = Math.max(...groupItems.map(item => new Date(item.updated_at).getTime()));
    const latestDate = new Date(latestTimestamp);
    
    return {
      id: isFileGroup ? firstItem.id : `group_${domain}`,
      title: isFileGroup ? firstItem.title : `${domain} (${groupItems.length} sources)`,
      domain: isFileGroup ? 'file' : domain,
      items: groupItems,
      metadata: {
        ...firstItem.metadata,
        // Merge tags from all items in the group
        tags: [...new Set(groupItems.flatMap(item => item.metadata.tags || []))],
      },
      created_at: firstItem.created_at,
      updated_at: latestDate.toISOString(),
    };
  });
};





export const KnowledgeBasePage = () => {
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [forceReanimate, setForceReanimate] = useState(0);
  const [typeFilter, setTypeFilter] = useState<'all' | 'technical' | 'business'>('all');
  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
  const [progressItems, setProgressItems] = useState<CrawlProgressData[]>([]);
  const [loading, setLoading] = useState(true);
  const [, setTotalItems] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [loadingStrategy, setLoadingStrategy] = useState<'websocket' | 'rest' | 'complete'>('rest');
  const searchTimeoutRef = useRef<NodeJS.Timeout>();
  const loadTimeoutRef = useRef<NodeJS.Timeout>();
  
  const { showToast } = useToast();

  // Single consolidated loading function
  const loadKnowledgeItems = async (options = {}) => {
    const startTime = Date.now();
    console.log('📊 Starting knowledge items API request...');
    
    try {
      setLoading(true);
      const response = await knowledgeBaseService.getKnowledgeItems({
        knowledge_type: typeFilter === 'all' ? undefined : typeFilter,
        search: searchQuery || undefined,
        page: currentPage,
        per_page: 20,
        ...options
      });
      
      const loadTime = Date.now() - startTime;
      console.log(`📊 API request completed successfully in ${loadTime}ms`);
      console.log(`📊 Loaded ${response.items.length} items out of ${response.total} total`);
      
      setKnowledgeItems(response.items);
      setTotalItems(response.total);
      setLoadingStrategy('complete');
    } catch (error) {
      const loadTime = Date.now() - startTime;
      console.error(`📊 API request failed after ${loadTime}ms:`, error);
      showToast('Failed to load knowledge items', 'error');
      setKnowledgeItems([]);
      setLoadingStrategy('complete');
    } finally {
      setLoading(false);
    }
  };

  // Initialize knowledge items on mount - load via REST API immediately
  useEffect(() => {
    console.log('🚀 KnowledgeBasePage: Loading knowledge items via REST API');
    
    // Load items immediately via REST API
    loadKnowledgeItems();
    
    return () => {
      console.log('🧹 KnowledgeBasePage: Cleaning up');
      // Clean up any active crawl progress connections if they exist
      crawlProgressService.disconnect();
    };
  }, []); // Only run once on mount

  // Handle filter changes
  useEffect(() => {
    if (loadingStrategy === 'complete') {
      // Filter changed, reloading knowledge items
      setCurrentPage(1);
      loadKnowledgeItems({ page: 1 });
      setForceReanimate(prev => prev + 1);
    }
  }, [typeFilter, loadingStrategy]);

  // Handle search with debounce
  useEffect(() => {
    if (loadingStrategy === 'complete') {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
      
      searchTimeoutRef.current = setTimeout(() => {
        console.log('🔎 Search query changed, reloading knowledge items');
        setCurrentPage(1);
        loadKnowledgeItems({ page: 1 });
      }, 500);
      
      return () => {
        if (searchTimeoutRef.current) {
          clearTimeout(searchTimeoutRef.current);
        }
      };
    }
  }, [searchQuery, loadingStrategy]);

  // Filter items based on selected type and search query
  const filteredItems = knowledgeItems.filter(item => {
    // Type filter
    const typeMatch = typeFilter === 'all' ? true : item.metadata.knowledge_type === typeFilter;
    
    // Search filter - search in title, description, tags, and source_id
    const searchMatch = !searchQuery || 
      item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (item.metadata.description && item.metadata.description.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (item.metadata.tags && item.metadata.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))) ||
      item.source_id.toLowerCase().includes(searchQuery.toLowerCase());
    
    return typeMatch && searchMatch;
  });

  // Group items by domain for grid view
  const groupedItems = viewMode === 'grid' ? groupItemsByDomain(filteredItems) : [];

  // Use our custom staggered entrance hook for the page header
  const {
    containerVariants: headerContainerVariants,
    itemVariants: headerItemVariants,
    titleVariants
  } = useStaggeredEntrance([1, 2], 0.15);

  // Separate staggered entrance for the content that will reanimate on view changes
  const {
    containerVariants: contentContainerVariants,
    itemVariants: contentItemVariants
  } = useStaggeredEntrance(filteredItems, 0.15, forceReanimate);

  const handleAddKnowledge = () => {
    setIsAddModalOpen(true);
  };

  const handleDeleteItem = async (sourceId: string) => {
    try {
      // Prevent duplicate operations by checking if already in progress
      if (loading) {
        // Delete already in progress, ignoring duplicate call
        return;
      }
      
      setLoading(true); // Set loading state to prevent duplicates
      
      // Check if this is a grouped item ID
      if (sourceId.startsWith('group_')) {
        // Find the grouped item and delete all its constituent items
        const domain = sourceId.replace('group_', '');
        const groupedItems = groupItemsByDomain(filteredItems);
        const group = groupedItems.find(g => g.domain === domain);
        
        if (group) {
          // Delete all items in the group
          for (const item of group.items) {
            await knowledgeBaseService.deleteKnowledgeItem(item.source_id);
          }
          showToast(`Deleted ${group.items.length} sources from ${domain}`, 'success');
        }
      } else {
        // Single item delete
        const result = await knowledgeBaseService.deleteKnowledgeItem(sourceId);
        showToast((result as any).message || 'Item deleted', 'success');
      }
      
      // Reload items without triggering WebSocket race condition
      await loadKnowledgeItems();
    } catch (error) {
      console.error('Failed to delete item:', error);
      showToast('Failed to delete item', 'error');
    } finally {
      setLoading(false); // Always reset loading state
    }
  };

  // Progress handling functions
  const handleProgressComplete = (data: CrawlProgressData) => {
    console.log('Crawl completed:', data);
    
    // Update the progress item to show completed state first
    setProgressItems(prev => 
      prev.map(item => 
        item.progressId === data.progressId 
          ? { ...data, status: 'completed', percentage: 100 }
          : item
      )
    );
    
    // Show success toast
    const message = data.uploadType === 'document' 
      ? `Document "${data.fileName}" uploaded successfully! ${data.chunksStored || 0} chunks stored.`
      : `Crawling completed for ${data.currentUrl}! ${data.chunksStored || 0} chunks stored.`;
    showToast(message, 'success');
    
    // Remove from progress items after a brief delay to show completion
    setTimeout(() => {
      setProgressItems(prev => prev.filter(item => item.progressId !== data.progressId));
      // Reload knowledge items to show the new item
      loadKnowledgeItems();
    }, 2000); // 2 second delay to show completion state
  };

  const handleProgressError = (error: string, progressId?: string) => {
    console.error('Crawl error:', error);
    showToast(`Crawling failed: ${error}`, 'error');
    
    // Auto-remove failed progress items after 5 seconds to prevent UI clutter
    if (progressId) {
      setTimeout(() => {
        setProgressItems(prev => prev.filter(item => item.progressId !== progressId));
      }, 5000);
    }
  };

  const handleProgressUpdate = (data: CrawlProgressData) => {
    setProgressItems(prev => 
      prev.map(item => 
        item.progressId === data.progressId ? data : item
      )
    );
  };

  const handleRetryProgress = (progressId: string) => {
    // Find the progress item and restart the crawl
    const progressItem = progressItems.find(item => item.progressId === progressId);
    if (progressItem) {
      // Remove the failed progress item
      setProgressItems(prev => prev.filter(item => item.progressId !== progressId));
      // This would typically trigger a new crawl - but that requires knowing the original URL
      showToast('Retry functionality not implemented yet', 'warning');
    }
  };

  const handleStartCrawl = async (progressId: string, initialData: Partial<CrawlProgressData>) => {
    // handleStartCrawl called with progressId
    // Initial data received
    
    const newProgressItem: CrawlProgressData = {
      progressId,
      status: 'starting',
      percentage: 0,
      logs: ['Starting crawl...'],
      ...initialData
    };
    
    // Adding progress item to state
    setProgressItems(prev => [...prev, newProgressItem]);
    
    // Set up callbacks for enhanced progress tracking
    const progressCallback = (data: CrawlProgressData) => {
      // Progress callback called
      
      if (data.progressId === progressId) {
        // Update progress first
        handleProgressUpdate(data);
        
        // Then handle completion/error states
        if (data.status === 'completed') {
          handleProgressComplete(data);
        } else if (data.status === 'error') {
          handleProgressError(data.error || 'Crawling failed', progressId);
        }
      }
    };
    
    const stateChangeCallback = (state: WebSocketState) => {
      // WebSocket state changed
      
      // Update UI based on connection state if needed
      if (state === WebSocketState.FAILED) {
        handleProgressError('Connection failed - please check your network', progressId);
      }
    };
    
    const errorCallback = (error: Error | Event) => {
      // WebSocket error
      const errorMessage = error instanceof Error ? error.message : 'Connection error';
      handleProgressError(`Connection error: ${errorMessage}`, progressId);
    };
    
    // Starting progress stream
    
    try {
      // Use the enhanced streamProgress method with all callbacks
      await crawlProgressService.streamProgressEnhanced(progressId, {
        onMessage: progressCallback,
        onStateChange: stateChangeCallback,
        onError: errorCallback
      }, {
        autoReconnect: true,
        reconnectDelay: 5000,
        connectionTimeout: 10000
      });
      
      // WebSocket connected successfully
      
      // Wait for connection to be fully established
      await crawlProgressService.waitForConnection(5000);
      
      // Connection verified
    } catch (error) {
      // Failed to establish WebSocket connection
      handleProgressError('Failed to connect to progress updates', progressId);
    }
  };

  return <div>
      {/* Header with animation - stays static when changing views */}
      <motion.div className="flex justify-between items-center mb-8" initial="hidden" animate="visible" variants={headerContainerVariants}>
        <motion.h1 className="text-3xl font-bold text-gray-800 dark:text-white flex items-center gap-3" variants={titleVariants}>
          <BookOpen className="w-7 h-7 text-green-500 filter drop-shadow-[0_0_8px_rgba(34,197,94,0.8)]" />
          Knowledge Base
        </motion.h1>
        <motion.div className="flex items-center gap-4" variants={headerItemVariants}>
          {/* Search Bar */}
          <div className="relative">
            <Input type="text" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Search knowledge base..." accentColor="purple" icon={<Search className="w-4 h-4" />} />
          </div>
          {/* Type Filter */}
          <div className="flex items-center bg-gray-50 dark:bg-black border border-gray-200 dark:border-zinc-900 rounded-md overflow-hidden">
            <button onClick={() => setTypeFilter('all')} className={`p-2 ${typeFilter === 'all' ? 'bg-gray-200 dark:bg-zinc-800 text-gray-800 dark:text-white' : 'text-gray-500 dark:text-zinc-500 hover:text-gray-700 dark:hover:text-zinc-300'}`} title="All Types">
              <Filter className="w-4 h-4" />
            </button>
            <button onClick={() => setTypeFilter('technical')} className={`p-2 ${typeFilter === 'technical' ? 'bg-blue-100 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400' : 'text-gray-500 dark:text-zinc-500 hover:text-gray-700 dark:hover:text-zinc-300'}`} title="Technical/Coding">
              <BoxIcon className="w-4 h-4" />
            </button>
            <button onClick={() => setTypeFilter('business')} className={`p-2 ${typeFilter === 'business' ? 'bg-purple-100 dark:bg-purple-500/10 text-purple-600 dark:text-purple-400' : 'text-gray-500 dark:text-zinc-500 hover:text-gray-700 dark:hover:text-zinc-300'}`} title="Business/Project">
              <Brain className="w-4 h-4" />
            </button>
          </div>
          {/* View Toggle */}
          <div className="flex items-center bg-gray-50 dark:bg-black border border-gray-200 dark:border-zinc-900 rounded-md overflow-hidden">
            <button onClick={() => setViewMode('grid')} className={`p-2 ${viewMode === 'grid' ? 'bg-purple-100 dark:bg-purple-500/10 text-purple-600 dark:text-purple-500' : 'text-gray-500 dark:text-zinc-500 hover:text-gray-700 dark:hover:text-zinc-300'}`} title="Grid View">
              <Grid className="w-4 h-4" />
            </button>
            <button onClick={() => setViewMode('table')} className={`p-2 ${viewMode === 'table' ? 'bg-blue-100 dark:bg-blue-500/10 text-blue-600 dark:text-blue-500' : 'text-gray-500 dark:text-zinc-500 hover:text-gray-700 dark:hover:text-zinc-300'}`} title="Table View">
              <List className="w-4 h-4" />
            </button>
          </div>
          {/* Add Button */}
          <Button onClick={handleAddKnowledge} variant="primary" accentColor="purple" className="shadow-lg shadow-purple-500/20">
            <Plus className="w-4 h-4 mr-2 inline" />
            <span>Knowledge</span>
          </Button>
        </motion.div>
      </motion.div>
      {/* Main Content */}
      <div className="relative">
        {loading ? (
          viewMode === 'table' ? <KnowledgeTableSkeleton /> : <KnowledgeGridSkeleton />
        ) : viewMode === 'table' ? (
          <KnowledgeTable 
            items={filteredItems} 
            onDelete={handleDeleteItem} 
          />
        ) : (
          <>
            {/* Knowledge Items Grid/List with staggered animation that reanimates on view change */}
            <AnimatePresence mode="wait">
              <motion.div key={`view-${viewMode}-filter-${typeFilter}`} initial="hidden" animate="visible" variants={contentContainerVariants} className={`grid ${viewMode === 'grid' ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4' : 'grid-cols-1 gap-3'}`}>
                {/* Progress Items */}
                {progressItems.map(progressData => (
                  <motion.div key={progressData.progressId} variants={contentItemVariants}>
                    <CrawlingProgressCard 
                      progressData={progressData}
                      onComplete={handleProgressComplete}
                      onError={(error) => handleProgressError(error, progressData.progressId)}
                      onProgress={handleProgressUpdate}
                      onRetry={() => handleRetryProgress(progressData.progressId)}
                      onDismiss={() => setProgressItems(prev => prev.filter(item => item.progressId !== progressData.progressId))}
                    />
                  </motion.div>
                ))}
                
                {/* Regular Knowledge Items */}
                {viewMode === 'grid' ? (
                  // Grid view - use grouped items
                  groupedItems.length > 0 ? groupedItems.map(groupedItem => (
                    <motion.div key={groupedItem.id} variants={contentItemVariants}>
                      <GroupedKnowledgeItemCard 
                        groupedItem={groupedItem} 
                        onDelete={handleDeleteItem}
                        onUpdate={loadKnowledgeItems} 
                      />
                    </motion.div>
                  )) : (progressItems.length === 0 && (
                    <motion.div variants={contentItemVariants} className="col-span-full py-10 text-center text-gray-500 dark:text-zinc-400">
                      No knowledge items found for the selected filter.
                    </motion.div>
                  ))
                ) : (
                  // List view - use individual items
                  filteredItems.length > 0 ? filteredItems.map(item => (
                    <motion.div key={item.id} variants={contentItemVariants}>
                      <KnowledgeItemCard item={item} onDelete={handleDeleteItem} onUpdate={loadKnowledgeItems} />
                    </motion.div>
                  )) : (progressItems.length === 0 && (
                    <motion.div variants={contentItemVariants} className="col-span-full py-10 text-center text-gray-500 dark:text-zinc-400">
                      No knowledge items found for the selected filter.
                    </motion.div>
                  ))
                )}
              </motion.div>
            </AnimatePresence>
          </>
        )}
      </div>
      {/* Add Knowledge Modal */}
      {isAddModalOpen && <AddKnowledgeModal 
        onClose={() => setIsAddModalOpen(false)} 
        onSuccess={() => {
          loadKnowledgeItems();
          setIsAddModalOpen(false);
        }}
        onStartCrawl={handleStartCrawl}
      />}
    </div>;
};





interface AddKnowledgeModalProps {
  onClose: () => void;
  onSuccess: () => void;
  onStartCrawl: (progressId: string, initialData: Partial<CrawlProgressData>) => void;
}

const AddKnowledgeModal = ({
  onClose,
  onSuccess,
  onStartCrawl
}: AddKnowledgeModalProps) => {
  const [method, setMethod] = useState<'url' | 'file'>('url');
  const [url, setUrl] = useState('');
  const [updateFrequency, setUpdateFrequency] = useState('7');
  const [tags, setTags] = useState<string[]>([]);
  const [newTag, setNewTag] = useState('');
  const [knowledgeType, setKnowledgeType] = useState<'technical' | 'business'>('technical');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [crawlDepth, setCrawlDepth] = useState(2);
  const [showDepthTooltip, setShowDepthTooltip] = useState(false);
  const { showToast } = useToast();

  // URL validation function that checks domain existence
  const validateUrl = async (url: string): Promise<{ isValid: boolean; error?: string; formattedUrl?: string }> => {
    try {
      // Basic format validation and URL formatting
      let formattedUrl = url.trim();
      if (!formattedUrl.startsWith('http://') && !formattedUrl.startsWith('https://')) {
        formattedUrl = `https://${formattedUrl}`;
      }
      
      // Check if it's a valid URL format
      let urlObj;
      try {
        urlObj = new URL(formattedUrl);
      } catch (urlError) {
        return { isValid: false, error: 'Please enter a valid URL format (e.g., https://example.com)' };
      }
      
      // Check if hostname has a valid domain structure
      const hostname = urlObj.hostname;
      if (!hostname || hostname === 'localhost' || /^\d+\.\d+\.\d+\.\d+$/.test(hostname)) {
        // Allow localhost and IP addresses for development
        return { isValid: true, formattedUrl };
      }
      
      // Check if domain has at least one dot (basic domain validation)
      if (!hostname.includes('.')) {
        return { isValid: false, error: 'Please enter a valid domain name (e.g., example.com)' };
      }
      
      // Check if domain has a valid TLD (at least 2 characters after the last dot)
      const parts = hostname.split('.');
      const tld = parts[parts.length - 1];
      if (tld.length < 2) {
        return { isValid: false, error: 'Please enter a valid domain with a proper extension (e.g., .com, .org)' };
      }
      
      // Basic DNS check by trying to resolve the domain
      try {
        const response = await fetch(`https://dns.google/resolve?name=${hostname}&type=A`, {
          method: 'GET',
          headers: { 'Accept': 'application/json' }
        });
        
        if (response.ok) {
          const dnsResult = await response.json();
          if (dnsResult.Status === 0 && dnsResult.Answer && dnsResult.Answer.length > 0) {
            return { isValid: true, formattedUrl };
          } else {
            return { isValid: false, error: `Domain "${hostname}" could not be resolved. Please check the URL.` };
          }
        } else {
          // If DNS check fails, allow the URL (might be a temporary DNS issue)
          console.warn('DNS check failed, allowing URL anyway:', hostname);
          return { isValid: true, formattedUrl };
        }
      } catch (dnsError) {
        // If DNS check fails, allow the URL (might be a network issue)
        console.warn('DNS check error, allowing URL anyway:', dnsError);
        return { isValid: true, formattedUrl };
      }
    } catch (error) {
      return { isValid: false, error: 'URL validation failed. Please check the URL format.' };
    }
  };

  const handleSubmit = async () => {
    try {
      setLoading(true);
      
      if (method === 'url') {
        if (!url.trim()) {
          showToast('Please enter a URL', 'error');
          return;
        }
        
        // Validate URL and check domain existence
        showToast('Validating URL...', 'info');
        const validation = await validateUrl(url);
        
        if (!validation.isValid) {
          showToast(validation.error || 'Invalid URL', 'error');
          return;
        }
        
        const formattedUrl = validation.formattedUrl!;
        setUrl(formattedUrl); // Update the input field to show the corrected URL
        
        const result = await knowledgeBaseService.crawlUrl({
          url: formattedUrl,
          knowledge_type: knowledgeType,
          tags,
          update_frequency: parseInt(updateFrequency),
          max_depth: crawlDepth
        });
        
        // Crawl URL result received
        
        // Check if result contains a progressId for streaming
        if ((result as any).progressId) {
          // Got progressId
          // About to call onStartCrawl function
          // onStartCrawl function ready
          
          // Start progress tracking
          onStartCrawl((result as any).progressId, {
            status: 'initializing',
            percentage: 0,
            currentStep: 'Starting crawl'
          });
          
          // onStartCrawl called successfully
          
          showToast('Crawling started - tracking progress', 'success');
          onClose(); // Close modal immediately
        } else {
          // No progressId in result
          // Result structure logged
          
          // Fallback for non-streaming response
          showToast((result as any).message || 'Crawling started', 'success');
          onSuccess();
        }
      } else {
        if (!selectedFile) {
          showToast('Please select a file', 'error');
          return;
        }
        
        const result = await knowledgeBaseService.uploadDocument(selectedFile, {
          knowledge_type: knowledgeType,
          tags
        });
        
        if (result.success && result.progressId) {
          // Upload started with progressId
          
          // Start progress tracking for upload
          onStartCrawl(result.progressId, {
            currentUrl: `file://${selectedFile.name}`,
            percentage: 0,
            status: 'starting',
            logs: [`Starting upload of ${selectedFile.name}`],
            uploadType: 'document',
            fileName: selectedFile.name,
            fileType: selectedFile.type
          });
          
          // onStartCrawl called successfully for upload
          
          showToast('Document upload started - tracking progress', 'success');
          onClose(); // Close modal immediately
        } else {
          // No progressId in upload result
          // Upload result structure logged
          
          // Fallback for non-streaming response
          showToast((result as any).message || 'Document uploaded successfully', 'success');
          onSuccess();
        }
      }
    } catch (error) {
      console.error('Failed to add knowledge:', error);
      showToast('Failed to add knowledge source', 'error');
    } finally {
      setLoading(false);
    }
  };

  return <div className="fixed inset-0 bg-gray-500/50 dark:bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-2xl relative before:content-[''] before:absolute before:top-0 before:left-0 before:w-full before:h-[1px] before:bg-green-500 p-8">
        <h2 className="text-xl font-bold text-gray-800 dark:text-white mb-8">
          Add Knowledge Source
        </h2>
        {/* Knowledge Type Selection */}
        <div className="mb-6">
          <label className="block text-gray-600 dark:text-zinc-400 text-sm mb-2">
            Knowledge Type
          </label>
          <div className="flex gap-4">
            <label className={`
                flex-1 p-4 rounded-md border cursor-pointer transition flex items-center justify-center gap-2
                ${knowledgeType === 'technical' ? 'border-blue-500 text-blue-600 dark:text-blue-500 bg-blue-50 dark:bg-blue-500/5' : 'border-gray-200 dark:border-zinc-900 text-gray-500 dark:text-zinc-400 hover:border-blue-300 dark:hover:border-blue-500/30'}
              `}>
              <input type="radio" name="knowledgeType" value="technical" checked={knowledgeType === 'technical'} onChange={() => setKnowledgeType('technical')} className="sr-only" />
              <BoxIcon className="w-5 h-5" />
              <span>Technical/Coding</span>
            </label>
            <label className={`
                flex-1 p-4 rounded-md border cursor-pointer transition flex items-center justify-center gap-2
                ${knowledgeType === 'business' ? 'border-purple-500 text-purple-600 dark:text-purple-500 bg-purple-50 dark:bg-purple-500/5' : 'border-gray-200 dark:border-zinc-900 text-gray-500 dark:text-zinc-400 hover:border-purple-300 dark:hover:border-purple-500/30'}
              `}>
              <input type="radio" name="knowledgeType" value="business" checked={knowledgeType === 'business'} onChange={() => setKnowledgeType('business')} className="sr-only" />
              <Brain className="w-5 h-5" />
              <span>Business/Project</span>
            </label>
          </div>
        </div>
        {/* Source Type Selection */}
        <div className="flex gap-4 mb-6">
          <button onClick={() => setMethod('url')} className={`flex-1 p-4 rounded-md border ${method === 'url' ? 'border-blue-500 text-blue-600 dark:text-blue-500 bg-blue-50 dark:bg-blue-500/5' : 'border-gray-200 dark:border-zinc-900 text-gray-500 dark:text-zinc-400 hover:border-blue-300 dark:hover:border-blue-500/30'} transition flex items-center justify-center gap-2`}>
            <LinkIcon className="w-4 h-4" />
            <span>URL / Website</span>
          </button>
          <button onClick={() => setMethod('file')} className={`flex-1 p-4 rounded-md border ${method === 'file' ? 'border-pink-500 text-pink-600 dark:text-pink-500 bg-pink-50 dark:bg-pink-500/5' : 'border-gray-200 dark:border-zinc-900 text-gray-500 dark:text-zinc-400 hover:border-pink-300 dark:hover:border-pink-500/30'} transition flex items-center justify-center gap-2`}>
            <Upload className="w-4 h-4" />
            <span>Upload File</span>
          </button>
        </div>
        {/* URL Input */}
        {method === 'url' && <div className="mb-6">
            <Input 
              label="URL to Scrape" 
              type="url" 
              value={url} 
              onChange={e => setUrl(e.target.value)} 
              placeholder="https://example.com or example.com" 
              accentColor="blue" 
            />
            {url && !url.startsWith('http://') && !url.startsWith('https://') && (
              <p className="text-amber-600 dark:text-amber-400 text-sm mt-1">
                ℹ️ Will automatically add https:// prefix
              </p>
            )}
          </div>}
        {/* File Upload */}
        {method === 'file' && (
          <div className="mb-6">
            <label className="block text-gray-600 dark:text-zinc-400 text-sm mb-2">
              Upload Document
            </label>
            <div className="relative">
              <input 
                id="file-upload"
                type="file"
                accept=".pdf,.md,.doc,.docx,.txt"
                onChange={e => setSelectedFile(e.target.files?.[0] || null)}
                className="sr-only"
              />
              <label 
                htmlFor="file-upload"
                className="flex items-center justify-center gap-3 w-full p-6 rounded-md border-2 border-dashed cursor-pointer transition-all duration-300
                  bg-blue-500/10 hover:bg-blue-500/20 
                  border-blue-500/30 hover:border-blue-500/50
                  text-blue-600 dark:text-blue-400
                  hover:shadow-[0_0_15px_rgba(59,130,246,0.3)]
                  backdrop-blur-sm"
              >
                <Upload className="w-6 h-6" />
                <div className="text-center">
                  <div className="font-medium">
                    {selectedFile ? selectedFile.name : 'Choose File'}
                  </div>
                  <div className="text-sm opacity-75 mt-1">
                    {selectedFile ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB` : 'Click to browse or drag and drop'}
                  </div>
                </div>
              </label>
            </div>
            <p className="text-gray-500 dark:text-zinc-600 text-sm mt-2">
              Supports PDF, MD, DOC up to 10MB
            </p>
          </div>
        )}
        {/* Crawl Depth - Only for URLs */}
        {method === 'url' && (
          <div className="mb-6">
            <label className="block text-gray-600 dark:text-zinc-400 text-sm mb-4">
              Crawl Depth
              <button
                type="button"
                className="ml-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                onMouseEnter={() => setShowDepthTooltip(true)}
                onMouseLeave={() => setShowDepthTooltip(false)}
              >
                <svg className="w-4 h-4 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </button>
            </label>
            
            <GlassCrawlDepthSelector
              value={crawlDepth}
              onChange={setCrawlDepth}
              showTooltip={showDepthTooltip}
              onTooltipToggle={setShowDepthTooltip}
            />
          </div>
        )}
        
        {/* Update Frequency */}
        {method === 'url' && <div className="mb-6">
            <Select label="Update Frequency" value={updateFrequency} onChange={e => setUpdateFrequency(e.target.value)} options={[{
          value: '1',
          label: 'Daily'
        }, {
          value: '7',
          label: 'Weekly'
        }, {
          value: '30',
          label: 'Monthly'
        }, {
          value: '0',
          label: 'Never'
        }]} accentColor="blue" />
          </div>}
        {/* Tags */}
        <div className="mb-6">
          <label className="block text-gray-600 dark:text-zinc-400 text-sm mb-2">
            Tags (AI will add recommended tags if left blank)
          </label>
          <div className="flex flex-wrap gap-2 mb-2">
            {tags.map(tag => <Badge key={tag} color="purple" variant="outline">
                {tag}
              </Badge>)}
          </div>
          <Input type="text" value={newTag} onChange={e => setNewTag(e.target.value)} onKeyDown={e => {
          if (e.key === 'Enter' && newTag.trim()) {
            setTags([...tags, newTag.trim()]);
            setNewTag('');
          }
        }} placeholder="Add tags..." accentColor="purple" />
        </div>
        {/* Action Buttons */}
        <div className="flex justify-end gap-4">
          <Button onClick={onClose} variant="ghost" disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} variant="primary" accentColor={method === 'url' ? 'blue' : 'pink'} disabled={loading}>
            {loading ? 'Adding...' : 'Add Source'}
          </Button>
        </div>
      </Card>
    </div>;
};

