import React, { useState, useEffect } from 'react';
import { ArrowRight, Plus, X, Search, Upload, Link as LinkIcon, Check, Filter, BoxIcon, Brain } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '../ui/Button';
import { knowledgeBaseService, KnowledgeItem } from '../../services/knowledgeBaseService';
import { useToast } from '../../contexts/ToastContext';
import { Input } from '../ui/Input';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Select } from '../ui/Select';
import { CrawlProgressData, crawlProgressService } from '../../services/crawlProgressService';

// Define Task interface locally to fix linter errors
interface Task {
  id: string;
  title: string;
  feature: string;
  status: 'backlog' | 'in-progress' | 'testing' | 'complete';
}
/* ——————————————————————————————————————————— */
/* Main component                                 */
/* ——————————————————————————————————————————— */
export const DocsTab = ({
  tasks
}: {
  tasks: Task[];
}) => {
  const [showTechnicalModal, setShowTechnicalModal] = useState(false);
  const [showBusinessModal, setShowBusinessModal] = useState(false);
  const [selectedTechnicalSources, setSelectedTechnicalSources] = useState<string[]>([]);
  const [selectedBusinessSources, setSelectedBusinessSources] = useState<string[]>([]);
  const [showAddSourceModal, setShowAddSourceModal] = useState(false);
  const [sourceType, setSourceType] = useState<'technical' | 'business'>('technical');
  const [knowledgeItems, setKnowledgeItems] = useState<KnowledgeItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [progressItems, setProgressItems] = useState<CrawlProgressData[]>([]);
  const { showToast } = useToast();

  // Load knowledge items from the service
  const loadKnowledgeItems = async (knowledgeType?: 'technical' | 'business') => {
    try {
      setLoading(true);
      const response = await knowledgeBaseService.getKnowledgeItems({
        knowledge_type: knowledgeType,
        page: 1,
        per_page: 50
      });
      setKnowledgeItems(response.items);
    } catch (error) {
      console.error('Failed to load knowledge items:', error);
      showToast('Failed to load knowledge items', 'error');
      setKnowledgeItems([]);
    } finally {
      setLoading(false);
    }
  };

  // Load knowledge items on component mount
  useEffect(() => {
    loadKnowledgeItems();
  }, []);

  // Transform KnowledgeItem to legacy format for compatibility
  const transformToLegacyFormat = (items: KnowledgeItem[]) => {
    return items.map(item => ({
      id: item.id,
      title: item.title,
      type: item.metadata.source_type || 'url',
      lastUpdated: new Date(item.updated_at).toLocaleDateString()
    }));
  };

  // Filter knowledge items by type
  const technicalSources = transformToLegacyFormat(
    knowledgeItems.filter(item => item.metadata.knowledge_type === 'technical')
  );
  
  const businessSources = transformToLegacyFormat(
    knowledgeItems.filter(item => item.metadata.knowledge_type === 'business')
  );
  // Toggle selection of a source
  const toggleTechnicalSource = (id: string) => {
    setSelectedTechnicalSources(prev => prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]);
  };
  const toggleBusinessSource = (id: string) => {
    setSelectedBusinessSources(prev => prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]);
  };
  // Save selected sources
  const saveTechnicalSources = () => {
    // Here you would handle saving the selected sources
    console.log('Saving technical sources:', selectedTechnicalSources);
    setShowTechnicalModal(false);
  };
  const saveBusinessSources = () => {
    // Here you would handle saving the selected sources
    console.log('Saving business sources:', selectedBusinessSources);
    setShowBusinessModal(false);
  };
  // Progress handling functions
  const handleProgressComplete = (data: CrawlProgressData) => {
    console.log('Crawl completed:', data);
    setProgressItems(prev => prev.filter(item => item.progressId !== data.progressId));
    loadKnowledgeItems(); // Reload knowledge items
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

  const handleStartCrawl = (progressId: string, initialData: Partial<CrawlProgressData>) => {
    console.log(`Starting crawl tracking for: ${progressId}`);
    
    const newProgressItem: CrawlProgressData = {
      progressId,
      status: 'starting',
      percentage: 0,
      logs: ['Starting crawl...'],
      ...initialData
    };
    
    setProgressItems(prev => [...prev, newProgressItem]);
    
    const progressCallback = (data: CrawlProgressData) => {
      console.log(`📨 Progress callback called for ${progressId}:`, data);
      
      if (data.progressId === progressId) {
        handleProgressUpdate(data);
        
        if (data.status === 'completed') {
          handleProgressComplete(data);
        } else if (data.status === 'error') {
          handleProgressError(data.error || 'Crawling failed');
        }
      }
    };
    
    crawlProgressService.streamProgress(progressId, progressCallback, {
      autoReconnect: true,
      reconnectDelay: 5000
    });
  };

  // Open add source modal with the correct type
  const openAddSourceModal = (type: 'technical' | 'business') => {
    setSourceType(type);
    setShowAddSourceModal(true);
  };
  return <div className="relative bg-white/30 dark:bg-black/50 backdrop-blur-lg border border-gray-200 dark:border-gray-800 rounded-lg p-8 min-h-[70vh]">
      {/* Background effects */}
      <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(to_bottom,rgba(59,130,246,0.01)_50%,transparent_50%)] bg-[length:100%_4px]" />
      <div className="absolute inset-0 pointer-events-none shadow-[inset_0_0_30px_rgba(59,130,246,0.05)]" />
      <div className="absolute inset-0 rounded-lg overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-blue-500 shadow-[0_0_10px_2px_rgba(59,130,246,0.4)] dark:shadow-[0_0_20px_5px_rgba(59,130,246,0.7)]"></div>
      </div>
      <div className="max-w-6xl mx-auto">
        {/* Project Overview Cards - Horizontally displayed at the top */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          <OverviewCard title="Project Status" value={calculateProjectStatus(tasks)} subtext={calculateProjectStatus(tasks) === 'Development' ? 'In active development' : calculateProjectStatus(tasks) === 'Complete' ? 'All tasks completed' : 'Planning phase'} color="blue" />
          <OverviewCard title="Feature Progress" value={`${calculateFeatureCompletion(tasks)}%`} subtext={`${Object.keys(tasks.reduce((acc, task) => ({
          ...acc,
          [task.feature]: true
        }), {})).length} features tracked`} color="purple" />
          <OverviewCard title="Tasks Overview" value={`${tasks.filter(t => t.status === 'complete').length}/${tasks.length}`} subtext={`${tasks.filter(t => t.status === 'in-progress').length} in progress, ${tasks.filter(t => t.status === 'testing').length} in testing`} color="pink" />
        </div>
        {/* Header */}
        <header className="mb-8 text-center">
          <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 text-transparent bg-clip-text mb-2">
            Project Requirements Document (PRD)
          </h2>
          <p className="text-gray-400">E-commerce Platform v1.0</p>
        </header>
        <div className="space-y-8">
          {/* Project Overview */}
          <Section title="Project Overview" color="blue">
            <p className="mb-3">
              A modern e-commerce platform built with React and Node.js,
              featuring a responsive UI, secure payment processing, and
              comprehensive product management.
            </p>
            <p>
              Target completion: <span className="text-blue-400">Q3 2024</span>
            </p>
          </Section>
          {/* Architecture and Tech Packages in two columns */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Architecture Column */}
            <Section title="Architecture" color="purple">
              <CodeBlock label="Frontend" color="blue">
                <li>React + TypeScript</li>
                <li>Redux for state management</li>
                <li>React Router for navigation</li>
                <li>Tailwind CSS for styling</li>
              </CodeBlock>
              <CodeBlock label="Backend" color="purple">
                <li>Node.js + Express</li>
                <li>MongoDB for database</li>
                <li>JWT for authentication</li>
                <li>RESTful API architecture</li>
              </CodeBlock>
              <CodeBlock label="DevOps" color="pink">
                <li>Docker for containerization</li>
                <li>CI/CD with GitHub Actions</li>
                <li>AWS for hosting</li>
              </CodeBlock>
            </Section>
            {/* Tech Packages Column */}
            <Section title="Tech Packages" color="pink">
              <CodeBlock label="Frontend Dependencies" color="blue">
                <li>react ^18.2.0</li>
                <li>react-dom ^18.2.0</li>
                <li>react-router-dom ^6.8.0</li>
                <li>@reduxjs/toolkit ^1.9.2</li>
                <li>axios ^1.3.0</li>
                <li>tailwindcss ^3.2.4</li>
                <li>stripe-js ^1.46.0</li>
              </CodeBlock>
              <CodeBlock label="Backend Dependencies" color="purple">
                <li>express ^4.18.2</li>
                <li>mongoose ^6.9.0</li>
                <li>jsonwebtoken ^9.0.0</li>
                <li>bcrypt ^5.1.0</li>
                <li>stripe ^11.9.0</li>
                <li>cors ^2.8.5</li>
                <li>dotenv ^16.0.3</li>
              </CodeBlock>
            </Section>
          </div>
          {/* Technical and Business Knowledge in two columns */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Technical Knowledge */}
            <KnowledgeSection title="Technical Knowledge" color="blue" sources={selectedTechnicalSources.map(id => technicalSources.find(source => source.id === id))} onAddClick={() => setShowTechnicalModal(true)} />
            {/* Business Knowledge */}
            <KnowledgeSection title="Business Knowledge" color="purple" sources={selectedBusinessSources.map(id => businessSources.find(source => source.id === id))} onAddClick={() => setShowBusinessModal(true)} />
          </div>
          {/* Coding Standards */}
          <Section title="Coding Standards" color="orange">
            <ul className="list-disc pl-5 space-y-2">
              <li>Follow Airbnb JavaScript Style Guide</li>
              <li>Use functional components with hooks</li>
              <li>Implement strict TypeScript typing</li>
              <li>Write unit tests for all components and services</li>
              <li>Document functions/components with JSDoc</li>
              <li>Use semantic HTML and ensure accessibility (WCAG 2.1)</li>
              <li>Implement robust error handling</li>
            </ul>
          </Section>
          {/* UI/UX Requirements */}
          <Section title="UI/UX Requirements" color="blue">
            <CodeBlock label="Color Palette" color="blue">
              <div className="flex gap-2 mb-4">
                {['#1a1a2e', '#16213e', '#0f3460', '#e94560', '#ffffff'].map(c => <div key={c} className="w-10 h-10 rounded flex items-center justify-center text-xs shadow-[0_0_10px_rgba(0,0,0,0.2)] transition-transform hover:scale-105" style={{
                background: c,
                color: c === '#ffffff' ? '#000' : '#fff'
              }}>
                      {c}
                    </div>)}
              </div>
            </CodeBlock>
            <CodeBlock label="Typography" color="purple">
              <li>Headings: Poppins (600, 700)</li>
              <li>Body: Inter (400, 500)</li>
              <li>Monospace: JetBrains Mono</li>
            </CodeBlock>
            <CodeBlock label="UI Components" color="pink">
              <li>Material UI as base component library</li>
              <li>Custom button and form components</li>
              <li>Responsive design (mobile → desktop)</li>
              <li>Dark-mode support</li>
            </CodeBlock>
          </Section>
        </div>
        {/* Call-to-Action */}
      </div>
      {/* Technical Sources Modal */}
      {showTechnicalModal && <SourceSelectionModal title="Select Technical Knowledge Sources" sources={technicalSources} selectedSources={selectedTechnicalSources} onToggleSource={toggleTechnicalSource} onSave={saveTechnicalSources} onClose={() => setShowTechnicalModal(false)} onAddSource={() => openAddSourceModal('technical')} />}
      {/* Business Sources Modal */}
      {showBusinessModal && <SourceSelectionModal title="Select Business Knowledge Sources" sources={businessSources} selectedSources={selectedBusinessSources} onToggleSource={toggleBusinessSource} onSave={saveBusinessSources} onClose={() => setShowBusinessModal(false)} onAddSource={() => openAddSourceModal('business')} />}
      {/* Add Source Modal */}
      {showAddSourceModal && <AddKnowledgeModal 
        sourceType={sourceType}
        onClose={() => setShowAddSourceModal(false)} 
        onSuccess={() => {
          loadKnowledgeItems();
          setShowAddSourceModal(false);
        }}
        onStartCrawl={handleStartCrawl}
      />}
    </div>;
};
/* ——————————————————————————————————————————— */
/* Helper components                              */
/* ——————————————————————————————————————————— */
const calculateProjectStatus = (tasks: Task[]) => {
  const hasInProgress = tasks.some(task => task.status === 'in-progress' || task.status === 'testing');
  const allComplete = tasks.every(task => task.status === 'complete');
  if (allComplete) return 'Complete';
  if (hasInProgress) return 'Development';
  return 'Planning';
};
const calculateFeatureCompletion = (tasks: Task[]) => {
  const featureStats = tasks.reduce((acc, task) => {
    if (!acc[task.feature]) {
      acc[task.feature] = {
        total: 0,
        complete: 0
      };
    }
    acc[task.feature].total++;
    if (task.status === 'complete') {
      acc[task.feature].complete++;
    }
    return acc;
  }, {} as Record<string, {
    total: number;
    complete: number;
  }>);
  const totalFeatures = Object.keys(featureStats).length;
  const completedFeatures = Object.values(featureStats).reduce((sum, {
    total,
    complete
  }) => sum + complete / total, 0);
  return Math.round(completedFeatures / totalFeatures * 100);
};
const calculateTaskDistribution = (tasks: Task[]) => {
  const distribution = tasks.reduce((acc, task) => {
    acc[task.status] = (acc[task.status] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  return {
    backlog: distribution.backlog || 0,
    inProgress: distribution['in-progress'] || 0,
    testing: distribution.testing || 0,
    complete: distribution.complete || 0
  };
};
const OverviewCard: React.FC<{
  title: string;
  value: string;
  subtext: string;
  color: 'blue' | 'purple' | 'pink';
}> = ({
  title,
  value,
  subtext,
  color
}) => {
  const colorMap = {
    blue: {
      bg: 'from-blue-400 via-blue-500 to-blue-400',
      glow: 'before:shadow-[0_0_10px_2px_rgba(59,130,246,0.4)] dark:before:shadow-[0_0_20px_5px_rgba(59,130,246,0.7)]',
      border: 'border-blue-300 dark:border-blue-500/30',
      text: 'text-blue-600 dark:text-blue-400',
      gradientFrom: 'from-blue-100 dark:from-blue-500/20',
      gradientTo: 'to-white dark:to-blue-500/5'
    },
    purple: {
      bg: 'from-purple-400 via-purple-500 to-purple-400',
      glow: 'before:shadow-[0_0_10px_2px_rgba(168,85,247,0.4)] dark:before:shadow-[0_0_20px_5px_rgba(168,85,247,0.7)]',
      border: 'border-purple-300 dark:border-purple-500/30',
      text: 'text-purple-600 dark:text-purple-400',
      gradientFrom: 'from-purple-100 dark:from-purple-500/20',
      gradientTo: 'to-white dark:to-purple-500/5'
    },
    pink: {
      bg: 'from-pink-400 via-pink-500 to-pink-400',
      glow: 'before:shadow-[0_0_10px_2px_rgba(236,72,153,0.4)] dark:before:shadow-[0_0_20px_5px_rgba(236,72,153,0.7)]',
      border: 'border-pink-300 dark:border-pink-500/30',
      text: 'text-pink-600 dark:text-pink-400',
      gradientFrom: 'from-pink-100 dark:from-pink-500/20',
      gradientTo: 'to-white dark:to-pink-500/5'
    }
  };
  return <div className={`
        relative p-4 rounded-md backdrop-blur-md
        bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30
        border ${colorMap[color].border}
        shadow-[0_10px_30px_-15px_rgba(0,0,0,0.1)] dark:shadow-[0_10px_30px_-15px_rgba(0,0,0,0.7)]
        hover:shadow-[0_15px_40px_-15px_rgba(0,0,0,0.2)] dark:hover:shadow-[0_15px_40px_-15px_rgba(0,0,0,0.9)]
        transition-all duration-300
        before:content-[""] before:absolute before:top-0 before:left-0 before:right-0 before:h-[2px] 
        before:rounded-t-[4px] before:bg-gradient-to-r ${colorMap[color].bg} ${colorMap[color].glow}
        after:content-[""] after:absolute after:top-0 after:left-0 after:right-0 after:h-16
        after:bg-gradient-to-b ${colorMap[color].gradientFrom} ${colorMap[color].gradientTo}
        after:rounded-t-md after:pointer-events-none
      `}>
      <div className="relative z-10">
        <h3 className="text-gray-600 dark:text-gray-400 text-sm mb-1">
          {title}
        </h3>
        <div className={`text-xl font-bold ${colorMap[color].text} mb-1`}>
          {value}
        </div>
        <p className="text-gray-500 dark:text-gray-500 text-xs">{subtext}</p>
      </div>
    </div>;
};
const Section: React.FC<{
  title: string;
  children: React.ReactNode;
  color: 'blue' | 'purple' | 'pink' | 'orange';
}> = ({
  title,
  children,
  color
}) => {
  const colorMap = {
    blue: 'bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.6)] dark:shadow-[0_0_8px_rgba(59,130,246,0.6)]',
    purple: 'bg-purple-400 shadow-[0_0_8px_rgba(168,85,247,0.6)] dark:shadow-[0_0_8px_rgba(168,85,247,0.6)]',
    pink: 'bg-pink-400 shadow-[0_0_8px_rgba(236,72,153,0.6)] dark:shadow-[0_0_8px_rgba(236,72,153,0.6)]',
    orange: 'bg-orange-400 shadow-[0_0_8px_rgba(249,115,22,0.6)] dark:shadow-[0_0_8px_rgba(249,115,22,0.6)]'
  };
  return <section>
      <h3 className="text-xl font-bold text-gray-800 dark:text-white mb-4 flex items-center">
        <span className={`w-2 h-2 rounded-full ${colorMap[color]} mr-2`} />
        {title}
      </h3>
      <div className="bg-white/50 dark:bg-black/30 border border-gray-200 dark:border-gray-800 rounded-lg p-4 font-mono text-sm text-gray-700 dark:text-gray-300 backdrop-blur-sm relative overflow-hidden">
        <div className="absolute top-0 left-0 right-0 h-[1px] bg-blue-500/30"></div>
        {children}
      </div>
    </section>;
};
const CodeBlock: React.FC<{
  label: string;
  children: React.ReactNode;
  color: 'blue' | 'purple' | 'pink';
}> = ({
  label,
  children,
  color
}) => {
  const colorMap = {
    blue: {
      text: 'text-blue-400',
      dot: 'bg-blue-400 shadow-[0_0_4px_rgba(59,130,246,0.6)]'
    },
    purple: {
      text: 'text-purple-400',
      dot: 'bg-purple-400 shadow-[0_0_4px_rgba(168,85,247,0.6)]'
    },
    pink: {
      text: 'text-pink-400',
      dot: 'bg-pink-400 shadow-[0_0_4px_rgba(236,72,153,0.6)]'
    }
  };
  return <div className="mb-6">
      <p className={`${colorMap[color].text} mb-2 flex items-center`}>
        <span className={`w-1 h-1 rounded-full ${colorMap[color].dot} mr-2`}></span>
        // {label}
      </p>
      <ul className="list-disc pl-5 space-y-1">{children}</ul>
    </div>;
};
// Knowledge Section Component
const KnowledgeSection: React.FC<{
  title: string;
  color: 'blue' | 'purple' | 'pink' | 'orange';
  sources: any[];
  onAddClick: () => void;
}> = ({
  title,
  color,
  sources = [],
  onAddClick
}) => {
  const colorMap = {
    blue: {
      bg: 'bg-blue-500/10',
      border: 'border-blue-500/30',
      text: 'text-blue-600 dark:text-blue-400',
      buttonBg: 'bg-blue-500/20',
      buttonHover: 'hover:bg-blue-500/30',
      buttonBorder: 'border-blue-500/40',
      buttonShadow: 'hover:shadow-[0_0_15px_rgba(59,130,246,0.3)]'
    },
    purple: {
      bg: 'bg-purple-500/10',
      border: 'border-purple-500/30',
      text: 'text-purple-600 dark:text-purple-400',
      buttonBg: 'bg-purple-500/20',
      buttonHover: 'hover:bg-purple-500/30',
      buttonBorder: 'border-purple-500/40',
      buttonShadow: 'hover:shadow-[0_0_15px_rgba(168,85,247,0.3)]'
    },
    pink: {
      bg: 'bg-pink-500/10',
      border: 'border-pink-500/30',
      text: 'text-pink-600 dark:text-pink-400',
      buttonBg: 'bg-pink-500/20',
      buttonHover: 'hover:bg-pink-500/30',
      buttonBorder: 'border-pink-500/40',
      buttonShadow: 'hover:shadow-[0_0_15px_rgba(236,72,153,0.3)]'
    },
    orange: {
      bg: 'bg-orange-500/10',
      border: 'border-orange-500/30',
      text: 'text-orange-600 dark:text-orange-400',
      buttonBg: 'bg-orange-500/20',
      buttonHover: 'hover:bg-orange-500/30',
      buttonBorder: 'border-orange-500/40',
      buttonShadow: 'hover:shadow-[0_0_15px_rgba(249,115,22,0.3)]'
    }
  };
  return <section>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-xl font-bold text-gray-800 dark:text-white flex items-center">
          <span className={`w-2 h-2 rounded-full bg-${color}-400 shadow-[0_0_8px_rgba(59,130,246,0.6)] mr-2`} />
          {title}
        </h3>
        <button onClick={onAddClick} className={`px-3 py-1.5 rounded-md ${colorMap[color].buttonBg} ${colorMap[color].buttonHover} border ${colorMap[color].buttonBorder} ${colorMap[color].text} ${colorMap[color].buttonShadow} transition-all duration-300 flex items-center gap-2`}>
          <Plus className="w-4 h-4" />
          <span className="text-sm">Add Sources</span>
        </button>
      </div>
      <div className={`bg-white/10 dark:bg-black/30 border ${colorMap[color].border} rounded-lg p-4 backdrop-blur-sm relative overflow-hidden min-h-[200px]`}>
        <div className="absolute top-0 left-0 right-0 h-[1px] bg-blue-500/30"></div>
        {sources && sources.length > 0 ? <div className="space-y-3">
            {sources.map(source => source && <div key={source.id} className="flex items-center gap-3 p-2 rounded-md bg-white/10 dark:bg-black/30 border border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700 transition-all">
                    {source.type === 'url' ? <LinkIcon className="w-4 h-4 text-blue-600 dark:text-blue-400" /> : <Upload className="w-4 h-4 text-pink-600 dark:text-pink-400" />}
                    <div className="flex-1">
                      <div className="text-gray-800 dark:text-white text-sm font-medium">
                        {source.title}
                      </div>
                      <div className="text-gray-500 text-xs">
                        Updated {source.lastUpdated}
                      </div>
                    </div>
                  </div>)}
          </div> : <div className="flex flex-col items-center justify-center h-[150px] text-gray-500">
            <p className="mb-2">No knowledge sources added yet</p>
            <p className="text-sm">
              Click "Add Sources" to select relevant documents
            </p>
          </div>}
      </div>
    </section>;
};
// Source Selection Modal
const SourceSelectionModal: React.FC<{
  title: string;
  sources: any[];
  selectedSources: string[];
  onToggleSource: (id: string) => void;
  onSave: () => void;
  onClose: () => void;
  onAddSource: () => void;
}> = ({
  title,
  sources,
  selectedSources,
  onToggleSource,
  onSave,
  onClose,
  onAddSource
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  // Filter sources based on search query
  const filteredSources = sources.filter(source => source.title.toLowerCase().includes(searchQuery.toLowerCase()));
  return <div className="fixed inset-0 bg-gray-500/50 dark:bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="relative p-6 rounded-md backdrop-blur-md w-full max-w-3xl
          bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30
          border border-gray-200 dark:border-zinc-800/50
          shadow-[0_10px_30px_-15px_rgba(0,0,0,0.1)] dark:shadow-[0_10px_30px_-15px_rgba(0,0,0,0.7)]
          before:content-[''] before:absolute before:top-0 before:left-0 before:right-0 before:h-[2px] 
          before:rounded-t-[4px] before:bg-blue-500 
          before:shadow-[0_0_10px_2px_rgba(59,130,246,0.4)] dark:before:shadow-[0_0_20px_5px_rgba(59,130,246,0.7)]
          after:content-[''] after:absolute after:top-0 after:left-0 after:right-0 after:h-16
          after:bg-gradient-to-b after:from-blue-100 after:to-white dark:after:from-blue-500/20 dark:after:to-blue-500/5
          after:rounded-t-md after:pointer-events-none">
        <div className="relative z-10">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 text-transparent bg-clip-text">
              {title}
            </h3>
            <button onClick={onClose} className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-white transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>
          {/* Search and Add Source */}
          <div className="flex gap-3 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 w-4 h-4" />
              <input type="text" value={searchQuery} onChange={e => setSearchQuery(e.target.value)} placeholder="Search sources..." className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white rounded-md py-2 pl-10 pr-3 focus:outline-none focus:border-blue-400 focus:shadow-[0_0_10px_rgba(59,130,246,0.2)] transition-all duration-300" />
            </div>
            <Button onClick={onAddSource} variant="primary" accentColor="blue" className="shadow-lg shadow-blue-500/20">
              <Plus className="w-4 h-4 mr-2 inline" />
              <span>Add Source</span>
            </Button>
          </div>
          {/* Sources List */}
          <div className="bg-white/50 dark:bg-black/50 border border-gray-200 dark:border-gray-800 rounded-md p-2 max-h-[50vh] overflow-y-auto mb-6">
            {filteredSources.length > 0 ? <div className="space-y-2">
                {filteredSources.map(source => <div key={source.id} onClick={() => onToggleSource(source.id)} className={`flex items-center gap-3 p-3 rounded-md cursor-pointer transition-all duration-200 
                      ${selectedSources.includes(source.id) ? 'bg-blue-100/80 dark:bg-blue-900/30 border border-blue-300 dark:border-blue-500/50' : 'bg-white/50 dark:bg-black/30 border border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'}`}>
                    <div className={`w-5 h-5 rounded-md border flex items-center justify-center 
                        ${selectedSources.includes(source.id) ? 'bg-blue-500 border-blue-500' : 'border-gray-400 dark:border-gray-600'}`}>
                      {selectedSources.includes(source.id) && <Check className="w-3 h-3 text-white" />}
                    </div>
                    {source.type === 'url' ? <LinkIcon className="w-4 h-4 text-blue-600 dark:text-blue-400" /> : <Upload className="w-4 h-4 text-pink-600 dark:text-pink-400" />}
                    <div className="flex-1">
                      <div className="text-gray-800 dark:text-white text-sm font-medium">
                        {source.title}
                      </div>
                      <div className="text-gray-500 dark:text-gray-500 text-xs">
                        Updated {source.lastUpdated}
                      </div>
                    </div>
                  </div>)}
              </div> : <div className="flex items-center justify-center h-32 text-gray-500 dark:text-gray-500">
                No sources found matching your search
              </div>}
          </div>
          {/* Action Buttons */}
          <div className="flex justify-end gap-3">
            <Button onClick={onClose} variant="ghost">
              Cancel
            </Button>
            <Button onClick={onSave} variant="primary" accentColor="blue" className="shadow-lg shadow-blue-500/20">
              Save Selected ({selectedSources.length})
            </Button>
          </div>
        </div>
      </div>
    </div>;
};
// Add Knowledge Modal Component (same as KnowledgeBasePage but with sourceType prop)
interface AddKnowledgeModalProps {
  sourceType: 'technical' | 'business';
  onClose: () => void;
  onSuccess: () => void;
  onStartCrawl: (progressId: string, initialData: Partial<CrawlProgressData>) => void;
}

const AddKnowledgeModal = ({
  sourceType,
  onClose,
  onSuccess,
  onStartCrawl
}: AddKnowledgeModalProps) => {
  const [method, setMethod] = useState<'url' | 'file'>('url');
  const [url, setUrl] = useState('');
  const [updateFrequency, setUpdateFrequency] = useState('7');
  const [tags, setTags] = useState<string[]>([]);
  const [newTag, setNewTag] = useState('');
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
        
        const result = await knowledgeBaseService.crawlUrl({
          url: url.trim(),
          knowledge_type: sourceType,
          tags,
          update_frequency: parseInt(updateFrequency)
        });
        
        // Check if result contains a progressId for streaming
        if ((result as any).progressId) {
          // Start progress tracking
          onStartCrawl((result as any).progressId, {
            currentUrl: url.trim(),
            totalPages: 0,
            processedPages: 0
          });
          
          showToast('Crawling started - tracking progress', 'success');
          onClose(); // Close modal immediately
        } else {
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
          knowledge_type: sourceType,
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
          Add {sourceType === 'technical' ? 'Technical' : 'Business'} Knowledge Source
        </h2>
        
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