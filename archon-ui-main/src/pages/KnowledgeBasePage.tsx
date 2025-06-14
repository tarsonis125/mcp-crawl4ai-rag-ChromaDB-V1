import React, { useEffect, useState, useRef } from 'react';
import { Search, Grid, List, Plus, Upload, Link as LinkIcon, Share2, Brain, Filter, BoxIcon, Trash2, TestTube, Table } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { MindMapView } from '../components/MindMapView';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Badge } from '../components/ui/Badge';
import { useStaggeredEntrance } from '../hooks/useStaggeredEntrance';
import { useToast } from '../contexts/ToastContext';
import { knowledgeBaseService, KnowledgeItem } from '../services/knowledgeBaseService';
import { performRAGQuery } from '../services/api';
import { KnowledgeItem as LegacyKnowledgeItem } from '../types/knowledge';
import { knowledgeWebSocket } from '../services/websocketService';
import { CrawlingProgressCard } from '../components/CrawlingProgressCard';
import { CrawlProgressData, crawlProgressService } from '../services/crawlProgressService';
import { KnowledgeTable } from '../components/knowledge-base/KnowledgeTable';

export const KnowledgeBasePage = () => {
  const [viewMode, setViewMode] = useState<'grid' | 'list' | 'mind-map' | 'table'>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [forceReanimate, setForceReanimate] = useState(0);
  const [typeFilter, setTypeFilter] = useState<'all' | 'technical' | 'business'>('all');
  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
  const [progressItems, setProgressItems] = useState<CrawlProgressData[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalItems, setTotalItems] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [loadingStrategy, setLoadingStrategy] = useState<'websocket' | 'rest' | 'complete'>('websocket');
  const searchTimeoutRef = useRef<NodeJS.Timeout>();
  const loadTimeoutRef = useRef<NodeJS.Timeout>();
  
  const { showToast } = useToast();

  // Single consolidated loading function
  const loadKnowledgeItems = async (options = {}) => {
    try {
      setLoading(true);
      const response = await knowledgeBaseService.getKnowledgeItems({
        knowledge_type: typeFilter === 'all' ? undefined : typeFilter,
        search: searchQuery || undefined,
        page: currentPage,
        per_page: 20,
        ...options
      });
      
      setKnowledgeItems(response.items);
      setTotalItems(response.total);
      setLoadingStrategy('complete');
    } catch (error) {
      console.error('Failed to load knowledge items:', error);
      showToast('Failed to load knowledge items', 'error');
      setKnowledgeItems([]);
      setLoadingStrategy('complete');
    } finally {
      setLoading(false);
    }
  };

  // Consolidated initialization effect - handles both WebSocket and fallback loading
  useEffect(() => {
    let isComponentMounted = true;
    let wsConnected = false;
    let fallbackExecuted = false;

    console.log('🚀 KnowledgeBasePage: Initializing data loading strategy');

    // Clear any existing timeouts
    if (loadTimeoutRef.current) {
      clearTimeout(loadTimeoutRef.current);
    }

    // Try WebSocket connection first
    const connectWebSocket = () => {
      console.log('📡 Attempting WebSocket connection for real-time updates');
      knowledgeWebSocket.connect('/api/knowledge-items/stream');
      
      const handleKnowledgeUpdate = (data: any) => {
        if (!isComponentMounted) return;
        
        if (data.type === 'knowledge_items_update') {
          console.log('✅ WebSocket: Received knowledge items update');
          setKnowledgeItems(data.data.items);
          setTotalItems(data.data.total);
          setLoading(false);
          setLoadingStrategy('websocket');
          wsConnected = true;
        }
      };
      
      knowledgeWebSocket.addEventListener('knowledge_items_update', handleKnowledgeUpdate);
      
      // Set fallback timeout - only execute if WebSocket hasn't connected and component is still mounted
      loadTimeoutRef.current = setTimeout(() => {
        if (isComponentMounted && !wsConnected && !fallbackExecuted) {
          console.log('⏰ WebSocket fallback: Loading via REST API after timeout');
          fallbackExecuted = true;
          loadKnowledgeItems();
        }
      }, 2000); // Reduced from 3000ms to 2000ms for better UX
      
      return () => {
        knowledgeWebSocket.removeEventListener('knowledge_items_update', handleKnowledgeUpdate);
      };
    };

    const cleanup = connectWebSocket();
    
    return () => {
      console.log('🧹 KnowledgeBasePage: Cleaning up data loading');
      isComponentMounted = false;
      if (loadTimeoutRef.current) {
        clearTimeout(loadTimeoutRef.current);
      }
      cleanup();
      knowledgeWebSocket.disconnect();
    };
  }, []); // Only run once on mount

  // Handle filter changes
  useEffect(() => {
    if (loadingStrategy === 'complete') {
      console.log('🔍 Filter changed, reloading knowledge items');
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

  // Filter items based on selected type
  const filteredItems = knowledgeItems.filter(item => 
    typeFilter === 'all' ? true : item.metadata.knowledge_type === typeFilter
  );

  // Use our custom staggered entrance hook for the page header
  const {
    isVisible: headerVisible,
    containerVariants: headerContainerVariants,
    itemVariants: headerItemVariants,
    titleVariants
  } = useStaggeredEntrance([1, 2], 0.15);

  // Separate staggered entrance for the content that will reanimate on view changes
  const {
    isVisible: contentVisible,
    containerVariants: contentContainerVariants,
    itemVariants: contentItemVariants
  } = useStaggeredEntrance(filteredItems, 0.15, forceReanimate);

  const handleAddKnowledge = () => {
    setIsAddModalOpen(true);
  };

  const handleDeleteItem = async (sourceId: string) => {
    try {
      const result = await knowledgeBaseService.deleteKnowledgeItem(sourceId);
      showToast((result as any).message || 'Item deleted', 'success');
      loadKnowledgeItems(); // Reload items
    } catch (error) {
      console.error('Failed to delete item:', error);
      showToast('Failed to delete item', 'error');
    }
  };

  // Progress handling functions
  const handleProgressComplete = (data: CrawlProgressData) => {
    console.log('Crawl completed:', data);
    // Remove from progress items
    setProgressItems(prev => prev.filter(item => item.progressId !== data.progressId));
    // Reload knowledge items to show the new item
    loadKnowledgeItems();
    showToast('Crawling completed successfully', 'success');
  };

  const handleProgressError = (error: string) => {
    console.error('Crawl error:', error);
    showToast(`Crawling failed: ${error}`, 'error');
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

  const handleStartCrawl = (progressId: string, initialData: Partial<CrawlProgressData>) => {
    console.log(`🚨 handleStartCrawl called with progressId: ${progressId}`);
    console.log(`🚨 Initial data:`, initialData);
    
    const newProgressItem: CrawlProgressData = {
      progressId,
      status: 'starting',
      percentage: 0,
      logs: ['Starting crawl...'],
      ...initialData
    };
    
    console.log(`🚨 Adding progress item to state`);
    setProgressItems(prev => [...prev, newProgressItem]);
    
    // Set up callbacks BEFORE connecting to ensure we don't miss any messages
    // Single unified callback that handles all progress states
    const progressCallback = (data: CrawlProgressData) => {
      console.log(`📨 Progress callback called for ${progressId}:`, data);
      
      if (data.progressId === progressId) {
        // Update progress first
        handleProgressUpdate(data);
        
        // Then handle completion/error states
        if (data.status === 'completed') {
          handleProgressComplete(data);
        } else if (data.status === 'error') {
          handleProgressError(data.error || 'Crawling failed');
        }
      }
    };
    
    console.log(`🚀 Starting progress stream for ${progressId}`);
    console.log(`🚀 About to call crawlProgressService.streamProgress`);
    
    try {
      // Use the new streamProgress method (matches MCP pattern)
      const ws = crawlProgressService.streamProgress(progressId, progressCallback, {
        autoReconnect: true,
        reconnectDelay: 5000
      });
      console.log(`🚀 streamProgress called, WebSocket:`, ws);
    } catch (error) {
      console.error(`❌ Error calling streamProgress:`, error);
    }
  };

  // Transform new KnowledgeItem format to legacy format for MindMapView
  const transformItemsForMindMap = (items: KnowledgeItem[]): LegacyKnowledgeItem[] => {
    return items.map(item => ({
      id: item.id,
      title: item.title,
      description: item.metadata.description || 'No description available',
      source: item.url,
      sourceType: item.metadata.source_type || 'url',
      sourceUrl: item.metadata.source_type === 'url' ? item.url : undefined,
      fileName: item.metadata.file_name,
      fileType: item.metadata.file_type,
      knowledgeType: item.metadata.knowledge_type || 'technical',
      tags: item.metadata.tags || [],
      lastUpdated: new Date(item.updated_at).toLocaleDateString(),
      nextUpdate: item.metadata.next_update,
      status: item.metadata.status || 'active',
      metadata: {
        size: `${item.metadata.chunks_count || 0} chunks`,
        pageCount: item.metadata.page_count,
        wordCount: item.metadata.word_count,
        lastScraped: item.metadata.last_scraped
      }
    }));
  };

  return <div>
      {/* Header with animation - stays static when changing views */}
      <motion.div className="flex justify-between items-center mb-8" initial="hidden" animate="visible" variants={headerContainerVariants}>
        <motion.h1 className="text-3xl font-bold text-gray-800 dark:text-white" variants={titleVariants}>
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
            <button onClick={() => setViewMode('list')} className={`p-2 ${viewMode === 'list' ? 'bg-green-100 dark:bg-green-500/10 text-green-600 dark:text-green-500' : 'text-gray-500 dark:text-zinc-500 hover:text-gray-700 dark:hover:text-zinc-300'}`} title="List View">
              <List className="w-4 h-4" />
            </button>
            <button onClick={() => setViewMode('table')} className={`p-2 ${viewMode === 'table' ? 'bg-blue-100 dark:bg-blue-500/10 text-blue-600 dark:text-blue-500' : 'text-gray-500 dark:text-zinc-500 hover:text-gray-700 dark:hover:text-zinc-300'}`} title="Table View">
              <Table className="w-4 h-4" />
            </button>
            <button onClick={() => setViewMode('mind-map')} className={`p-2 ${viewMode === 'mind-map' ? 'bg-blue-100 dark:bg-blue-500/10 text-blue-600 dark:text-blue-500' : 'text-gray-500 dark:text-zinc-500 hover:text-gray-700 dark:hover:text-zinc-300'}`} title="Mind Map View">
              <Share2 className="w-4 h-4" />
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
          <div className="flex flex-col justify-center items-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500 mb-3"></div>
            <p className="text-sm text-gray-500 dark:text-zinc-400">
              {loadingStrategy === 'websocket' ? 'Connecting to live updates...' : 'Loading knowledge items...'}
            </p>
          </div>
        ) : viewMode === 'mind-map' ? <MindMapView items={transformItemsForMindMap(filteredItems)} /> : 
        viewMode === 'table' ? (
          <KnowledgeTable 
            items={filteredItems} 
            onDelete={handleDeleteItem} 
            onTest={(item) => {
              // Implement test functionality here, perhaps by opening the TestKnowledgeModal
              console.log('Test item:', item);
            }}
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
                      onError={handleProgressError}
                      onProgress={handleProgressUpdate}
                      onRetry={() => handleRetryProgress(progressData.progressId)}
                    />
                  </motion.div>
                ))}
                
                {/* Regular Knowledge Items */}
                {filteredItems.length > 0 ? filteredItems.map(item => <motion.div key={item.id} variants={contentItemVariants}>
                      <KnowledgeItemCard item={item} viewMode={viewMode} onDelete={handleDeleteItem} />
                    </motion.div>) : (progressItems.length === 0 && <motion.div variants={contentItemVariants} className="col-span-full py-10 text-center text-gray-500 dark:text-zinc-400">
                    No knowledge items found for the selected filter.
                  </motion.div>)}
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

interface KnowledgeItemCardProps {
  item: KnowledgeItem;
  viewMode: 'grid' | 'list' | 'table';
  onDelete: (sourceId: string) => void;
}

const KnowledgeItemCard = ({
  item,
  viewMode,
  onDelete
}: KnowledgeItemCardProps) => {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showTestModal, setShowTestModal] = useState(false);

  const statusColorMap = {
    active: 'green',
    processing: 'blue',
    error: 'pink'
  };
  const accentColor = item.metadata.source_type === 'url' ? 'blue' : 'pink';
  
  // Get the type icon
  const TypeIcon = item.metadata.knowledge_type === 'technical' ? BoxIcon : Brain;
  const typeIconColor = item.metadata.knowledge_type === 'technical' ? 'text-blue-500' : 'text-purple-500';

  const handleDelete = () => {
    onDelete(item.source_id);
    setShowDeleteConfirm(false);
  };

  if (viewMode === 'list') {
    return <Card accentColor={accentColor} className="flex items-center gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            {/* Source type icon */}
            {item.metadata.source_type === 'url' ? <LinkIcon className="w-4 h-4 text-blue-500" /> : <Upload className="w-4 h-4 text-pink-500" />}
            {/* Knowledge type icon */}
            <TypeIcon className={`w-4 h-4 ${typeIconColor}`} />
            <h3 className="text-gray-800 dark:text-white font-medium">
              {item.title}
            </h3>
          </div>
          <p className="text-gray-600 dark:text-zinc-400 text-sm mb-2">
            {item.metadata.description || 'No description available'}
          </p>
          <div className="flex flex-wrap gap-2 mb-2">
            {item.metadata.tags?.map(tag => <Badge key={tag} color="purple" variant="outline">
                {tag}
              </Badge>) || null}
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-zinc-500">
            <span>Last updated: {new Date(item.updated_at).toLocaleDateString()}</span>
            <span>Chunks: {item.metadata.chunks_count || 0}</span>
            <Badge color={statusColorMap[item.metadata.status || 'active'] as any}>
              {(item.metadata.status || 'active').charAt(0).toUpperCase() + (item.metadata.status || 'active').slice(1)}
            </Badge>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowTestModal(true)} className="p-2 text-gray-500 hover:text-blue-500" title="Test with Query">
            <TestTube className="w-4 h-4" />
          </button>
          <button onClick={() => setShowDeleteConfirm(true)} className="p-2 text-gray-500 hover:text-red-500" title="Delete">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
        {showDeleteConfirm && <DeleteConfirmModal onConfirm={handleDelete} onCancel={() => setShowDeleteConfirm(false)} />}
        {showTestModal && <TestKnowledgeModal item={item} onClose={() => setShowTestModal(false)} />}
      </Card>;
  }

  return <Card accentColor={accentColor}>
      <div className="flex items-center gap-2 mb-3">
        {/* Source type icon */}
        {item.metadata.source_type === 'url' ? <LinkIcon className="w-4 h-4 text-blue-500" /> : <Upload className="w-4 h-4 text-pink-500" />}
        {/* Knowledge type icon */}
        <TypeIcon className={`w-4 h-4 ${typeIconColor}`} />
        <h3 className="text-gray-800 dark:text-white font-medium flex-1">
          {item.title}
        </h3>
        <div className="flex items-center gap-1">
          <button onClick={() => setShowTestModal(true)} className="p-1 text-gray-500 hover:text-blue-500" title="Test with Query">
            <TestTube className="w-3 h-3" />
          </button>
          <button onClick={() => setShowDeleteConfirm(true)} className="p-1 text-gray-500 hover:text-red-500" title="Delete">
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>
      <p className="text-gray-600 dark:text-zinc-400 text-sm mb-4 line-clamp-2">
        {item.metadata.description || 'No description available'}
      </p>
      <div className="flex flex-wrap gap-2 mb-4">
        {item.metadata.tags?.map(tag => <Badge key={tag} color="purple" variant="outline">
            {tag}
          </Badge>) || null}
      </div>
      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-zinc-500">
        <span>Updated: {new Date(item.updated_at).toLocaleDateString()}</span>
        <Badge color={statusColorMap[item.metadata.status || 'active'] as any}>
          {(item.metadata.status || 'active').charAt(0).toUpperCase() + (item.metadata.status || 'active').slice(1)}
        </Badge>
      </div>
      {showDeleteConfirm && <DeleteConfirmModal onConfirm={handleDelete} onCancel={() => setShowDeleteConfirm(false)} />}
      {showTestModal && <TestKnowledgeModal item={item} onClose={() => setShowTestModal(false)} />}
    </Card>;
};

interface DeleteConfirmModalProps {
  onConfirm: () => void;
  onCancel: () => void;
}

const DeleteConfirmModal = ({ onConfirm, onCancel }: DeleteConfirmModalProps) => {
  return <div className="fixed inset-0 bg-gray-500/50 dark:bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
    <Card className="w-full max-w-md">
      <h3 className="text-lg font-semibold text-gray-800 dark:text-white mb-4">
        Delete Knowledge Item
      </h3>
      <p className="text-gray-600 dark:text-zinc-400 mb-6">
        Are you sure you want to delete this knowledge item? This action cannot be undone.
      </p>
      <div className="flex justify-end gap-4">
        <Button onClick={onCancel} variant="ghost">
          Cancel
        </Button>
        <Button onClick={onConfirm} variant="primary" accentColor="pink">
          Delete
        </Button>
      </div>
    </Card>
  </div>;
};

interface TestKnowledgeModalProps {
  item: KnowledgeItem;
  onClose: () => void;
}

const TestKnowledgeModal = ({ item, onClose }: TestKnowledgeModalProps) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const { showToast } = useToast();

  const handleSearch = async () => {
    if (!query.trim()) return;
    
    try {
      setLoading(true);
      const response = await performRAGQuery(query, {
        source: item.source_id
      });
      setResults(response.results || []);
    } catch (error) {
      console.error('Failed to test query:', error);
      showToast('Failed to test query', 'error');
    } finally {
      setLoading(false);
    }
  };

  return <div className="fixed inset-0 bg-gray-500/50 dark:bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
    <Card className="w-full max-w-2xl max-h-[80vh] overflow-y-auto">
      <h3 className="text-lg font-semibold text-gray-800 dark:text-white mb-4">
        Test Knowledge Source
      </h3>
      <p className="text-gray-600 dark:text-zinc-400 mb-4">
        Testing: {item.title}
      </p>
      
      <div className="flex gap-2 mb-4">
        <Input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Enter a test query..."
          className="flex-1"
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
        />
        <Button onClick={handleSearch} disabled={loading || !query.trim()}>
          {loading ? 'Searching...' : 'Search'}
        </Button>
      </div>
      
      {results.length > 0 && (
        <div className="space-y-3 mb-4">
          <h4 className="font-medium text-gray-800 dark:text-white">Results:</h4>
          {results.map((result, index) => (
            <div key={index} className="p-3 bg-gray-50 dark:bg-zinc-900 rounded-md">
              <p className="text-sm text-gray-700 dark:text-zinc-300">{result.content}</p>
              <div className="mt-2 text-xs text-gray-500 dark:text-zinc-500">
                Score: {(result.score * 100).toFixed(1)}%
              </div>
            </div>
          ))}
        </div>
      )}
      
      <div className="flex justify-end">
        <Button onClick={onClose} variant="ghost">
          Close
        </Button>
      </div>
    </Card>
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
  const { showToast } = useToast();

  const handleSubmit = async () => {
    try {
      setLoading(true);
      
      if (method === 'url') {
        if (!url.trim()) {
          showToast('Please enter a URL', 'error');
          return;
        }
        
        // Validate and format URL
        let formattedUrl = url.trim();
        if (!formattedUrl.startsWith('http://') && !formattedUrl.startsWith('https://')) {
          // Auto-prepend https:// if no protocol is specified
          formattedUrl = `https://${formattedUrl}`;
          setUrl(formattedUrl); // Update the input field to show the corrected URL
        }
        
        // Additional validation to ensure it's a valid URL format
        try {
          new URL(formattedUrl);
        } catch (urlError) {
          showToast('Please enter a valid URL (e.g., https://example.com)', 'error');
          return;
        }
        
        const result = await knowledgeBaseService.crawlUrl({
          url: formattedUrl,
          knowledge_type: knowledgeType,
          tags,
          update_frequency: parseInt(updateFrequency)
        });
        
        console.log('🔍 Crawl URL result:', result);
        
        // Check if result contains a progressId for streaming
        if ((result as any).progressId) {
          console.log('✅ Got progressId:', (result as any).progressId);
          console.log('✅ About to call onStartCrawl function');
          console.log('✅ onStartCrawl function is:', onStartCrawl);
          
          // Start progress tracking
          onStartCrawl((result as any).progressId, {
            currentUrl: formattedUrl,
            totalPages: 0,
            processedPages: 0
          });
          
          console.log('✅ onStartCrawl called successfully');
          
          showToast('Crawling started - tracking progress', 'success');
          onClose(); // Close modal immediately
        } else {
          console.log('❌ No progressId in result');
          console.log('❌ Result structure:', JSON.stringify(result, null, 2));
          
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
        
        showToast((result as any).message || 'Document uploaded successfully', 'success');
        onSuccess();
      }
    } catch (error) {
      console.error('Failed to add knowledge:', error);
      showToast('Failed to add knowledge source', 'error');
    } finally {
      setLoading(false);
    }
  };

  return <div className="fixed inset-0 bg-gray-500/50 dark:bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
      <Card className="w-full max-w-2xl relative before:content-[''] before:absolute before:top-0 before:left-0 before:w-full before:h-[1px] before:bg-green-500">
        <h2 className="text-xl font-bold text-gray-800 dark:text-white mb-6">
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
        {method === 'file' &&           <div className="mb-6">
            <label htmlFor="file-upload" className="block text-gray-600 dark:text-zinc-400 text-sm mb-2">
              Upload Document
            </label>
            <input 
              id="file-upload"
              type="file"
              accept=".pdf,.md,.doc,.docx,.txt"
              onChange={e => setSelectedFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100"
            />
            <p className="text-gray-500 dark:text-zinc-600 text-sm mt-1">
              Supports PDF, MD, DOC up to 10MB
            </p>
          </div>}
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
            Tags
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