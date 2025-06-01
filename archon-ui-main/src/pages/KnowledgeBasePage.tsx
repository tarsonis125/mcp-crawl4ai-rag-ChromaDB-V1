import React, { useEffect, useState, Component } from 'react';
import { Search, Grid, List, Plus, Upload, Link as LinkIcon, Share2, Brain, Filter, BoxIcon } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { MindMapView } from '../components/MindMapView';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { Badge } from '../components/ui/Badge';
import { useStaggeredEntrance } from '../hooks/useStaggeredEntrance';
import { KnowledgeItem } from '../types/knowledge';
interface KnowledgeItem {
  id: string;
  title: string;
  description: string;
  source: string;
  sourceType: 'url' | 'file';
  sourceUrl?: string;
  fileName?: string;
  fileType?: string;
  tags: string[];
  lastUpdated: string;
  nextUpdate?: string;
  status: 'active' | 'processing' | 'error';
  metadata: {
    size: string;
    pageCount?: number;
    wordCount?: number;
    lastScraped?: string;
  };
  knowledgeType: 'technical' | 'business';
}
export const KnowledgeBasePage = () => {
  const [viewMode, setViewMode] = useState<'grid' | 'list' | 'mind-map'>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [forceReanimate, setForceReanimate] = useState(0);
  const [typeFilter, setTypeFilter] = useState<'all' | 'technical' | 'business'>('all');
  // Sample data - would come from API
  const [knowledgeItems] = useState<KnowledgeItem[]>([{
    id: '1',
    title: 'React Component Design Patterns',
    description: 'A comprehensive guide to React component patterns and best practices for scalable applications.',
    source: 'https://docs.example.com/react-patterns',
    sourceType: 'url',
    sourceUrl: 'https://docs.example.com/react-patterns',
    knowledgeType: 'technical',
    tags: ['react', 'patterns', 'frontend'],
    lastUpdated: '2024-01-20',
    nextUpdate: '2024-02-20',
    status: 'active',
    metadata: {
      size: '1.2 MB',
      wordCount: 5000,
      lastScraped: '2024-01-20'
    }
  }, {
    id: '2',
    title: 'System Architecture Guidelines',
    description: 'Internal documentation for system architecture and design principles.',
    source: 'architecture.pdf',
    sourceType: 'file',
    fileName: 'architecture.pdf',
    fileType: 'pdf',
    knowledgeType: 'technical',
    tags: ['architecture', 'system-design', 'internal'],
    lastUpdated: '2024-01-15',
    status: 'active',
    metadata: {
      size: '2.4 MB',
      pageCount: 45,
      wordCount: 12000
    }
  }, {
    id: '3',
    title: 'Project Management Framework',
    description: 'Business guidelines for managing complex projects and team coordination.',
    source: 'project-framework.pdf',
    sourceType: 'file',
    fileName: 'project-framework.pdf',
    fileType: 'pdf',
    knowledgeType: 'business',
    tags: ['project', 'management', 'business'],
    lastUpdated: '2024-01-18',
    status: 'active',
    metadata: {
      size: '1.8 MB',
      pageCount: 32,
      wordCount: 8500
    }
  }]);
  // Filter items based on selected type
  const filteredItems = knowledgeItems.filter(item => typeFilter === 'all' || item.knowledgeType === typeFilter);
  // Trigger reanimation when view mode changes
  useEffect(() => {
    setForceReanimate(prev => prev + 1);
  }, [viewMode, typeFilter]);
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
            <button onClick={() => setViewMode('mind-map')} className={`p-2 ${viewMode === 'mind-map' ? 'bg-blue-100 dark:bg-blue-500/10 text-blue-600 dark:text-blue-500' : 'text-gray-500 dark:text-zinc-500 hover:text-gray-700 dark:hover:text-zinc-300'}`} title="Mind Map View">
              <Share2 className="w-4 h-4" />
            </button>
          </div>
          {/* Add Button */}
          <Button onClick={() => setIsAddModalOpen(true)} variant="primary" accentColor="purple" className="shadow-lg shadow-purple-500/20">
            <Plus className="w-4 h-4 mr-2 inline" />
            <span>Knowledge</span>
          </Button>
        </motion.div>
      </motion.div>
      {/* Main Content */}
      <div className="relative">
        {viewMode === 'mind-map' ? <MindMapView items={filteredItems} /> : <>
            {/* Knowledge Items Grid/List with staggered animation that reanimates on view change */}
            <AnimatePresence mode="wait">
              <motion.div key={`view-${viewMode}-filter-${typeFilter}`} initial="hidden" animate="visible" variants={contentContainerVariants} className={`grid ${viewMode === 'grid' ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4' : 'grid-cols-1 gap-3'}`}>
                {filteredItems.length > 0 ? filteredItems.map(item => <motion.div key={item.id} variants={contentItemVariants}>
                      <KnowledgeItemCard item={item} viewMode={viewMode} />
                    </motion.div>) : <motion.div variants={contentItemVariants} className="col-span-full py-10 text-center text-gray-500 dark:text-zinc-400">
                    No knowledge items found for the selected filter.
                  </motion.div>}
              </motion.div>
            </AnimatePresence>
          </>}
      </div>
      {/* Add Knowledge Modal */}
      {isAddModalOpen && <AddKnowledgeModal onClose={() => setIsAddModalOpen(false)} />}
    </div>;
};
interface KnowledgeItemCardProps {
  item: KnowledgeItem;
  viewMode: 'grid' | 'list';
}
const KnowledgeItemCard = ({
  item,
  viewMode
}: KnowledgeItemCardProps) => {
  const statusColorMap = {
    active: 'green',
    processing: 'blue',
    error: 'pink'
  };
  const accentColor = item.sourceType === 'url' ? 'blue' : 'pink';
  // Get the type icon
  const TypeIcon = item.knowledgeType === 'technical' ? BoxIcon : Brain;
  const typeIconColor = item.knowledgeType === 'technical' ? 'text-blue-500' : 'text-purple-500';
  if (viewMode === 'list') {
    return <Card accentColor={accentColor} className="flex items-center gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            {/* Source type icon */}
            {item.sourceType === 'url' ? <LinkIcon className="w-4 h-4 text-blue-500" /> : <Upload className="w-4 h-4 text-pink-500" />}
            {/* Knowledge type icon */}
            <TypeIcon className={`w-4 h-4 ${typeIconColor}`} />
            <h3 className="text-gray-800 dark:text-white font-medium">
              {item.title}
            </h3>
          </div>
          <p className="text-gray-600 dark:text-zinc-400 text-sm mb-2">
            {item.description}
          </p>
          <div className="flex flex-wrap gap-2 mb-2">
            {item.tags.map(tag => <Badge key={tag} color="purple" variant="outline">
                {tag}
              </Badge>)}
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-zinc-500">
            <span>Last updated: {item.lastUpdated}</span>
            <span>Size: {item.metadata.size}</span>
            <Badge color={statusColorMap[item.status] as any}>
              {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
            </Badge>
          </div>
        </div>
      </Card>;
  }
  return <Card accentColor={accentColor}>
      <div className="flex items-center gap-2 mb-3">
        {/* Source type icon */}
        {item.sourceType === 'url' ? <LinkIcon className="w-4 h-4 text-blue-500" /> : <Upload className="w-4 h-4 text-pink-500" />}
        {/* Knowledge type icon */}
        <TypeIcon className={`w-4 h-4 ${typeIconColor}`} />
        <h3 className="text-gray-800 dark:text-white font-medium">
          {item.title}
        </h3>
      </div>
      <p className="text-gray-600 dark:text-zinc-400 text-sm mb-4 line-clamp-2">
        {item.description}
      </p>
      <div className="flex flex-wrap gap-2 mb-4">
        {item.tags.map(tag => <Badge key={tag} color="purple" variant="outline">
            {tag}
          </Badge>)}
      </div>
      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-zinc-500">
        <span>Updated: {item.lastUpdated}</span>
        <Badge color={statusColorMap[item.status] as any}>
          {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
        </Badge>
      </div>
    </Card>;
};
interface AddKnowledgeModalProps {
  onClose: () => void;
}
const AddKnowledgeModal = ({
  onClose
}: AddKnowledgeModalProps) => {
  const [method, setMethod] = useState<'url' | 'file'>('url');
  const [url, setUrl] = useState('');
  const [updateFrequency, setUpdateFrequency] = useState('7');
  const [tags, setTags] = useState<string[]>([]);
  const [newTag, setNewTag] = useState('');
  const [knowledgeType, setKnowledgeType] = useState<'technical' | 'business'>('technical');
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
            <Input label="URL to Scrape" type="url" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://..." accentColor="blue" />
          </div>}
        {/* File Upload */}
        {method === 'file' && <div className="mb-6">
            <label className="block text-gray-600 dark:text-zinc-400 text-sm mb-2">
              Upload Document
            </label>
            <div className="border border-dashed border-gray-300 dark:border-zinc-800 rounded-md p-8 text-center hover:border-pink-300 dark:hover:border-pink-500/50 transition-colors bg-gray-50 dark:bg-black/30">
              <Upload className="w-8 h-8 text-gray-400 dark:text-zinc-700 mx-auto mb-2" />
              <p className="text-gray-600 dark:text-zinc-400">
                Drag and drop your file here, or{' '}
                <span className="text-pink-600 dark:text-pink-500">browse</span>
              </p>
              <p className="text-gray-500 dark:text-zinc-600 text-sm mt-1">
                Supports PDF, MD, DOC up to 10MB
              </p>
            </div>
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
          if (e.key === 'Enter' && newTag) {
            setTags([...tags, newTag]);
            setNewTag('');
          }
        }} placeholder="Add tags..." accentColor="purple" />
        </div>
        {/* Action Buttons */}
        <div className="flex justify-end gap-4">
          <Button onClick={onClose} variant="ghost">
            Cancel
          </Button>
          <Button variant="primary" accentColor={method === 'url' ? 'blue' : 'pink'}>
            Add Source
          </Button>
        </div>
      </Card>
    </div>;
};