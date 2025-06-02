import React, { useState, Component } from 'react';
import { ArrowRight, Plus, X, Search, Upload, Link as LinkIcon, Check, Filter } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '../ui/Button';
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
  // Sample knowledge sources
  const technicalSources = [{
    id: 't1',
    title: 'React Component Design Patterns',
    type: 'url',
    lastUpdated: '2 days ago'
  }, {
    id: 't2',
    title: 'System Architecture Guidelines',
    type: 'pdf',
    lastUpdated: '5 days ago'
  }, {
    id: 't3',
    title: 'API Documentation',
    type: 'url',
    lastUpdated: '1 week ago'
  }, {
    id: 't4',
    title: 'Database Schema Reference',
    type: 'pdf',
    lastUpdated: '2 weeks ago'
  }, {
    id: 't5',
    title: 'Frontend Testing Framework',
    type: 'url',
    lastUpdated: '3 days ago'
  }];
  const businessSources = [{
    id: 'b1',
    title: 'Project Management Framework',
    type: 'pdf',
    lastUpdated: '1 day ago'
  }, {
    id: 'b2',
    title: 'Market Analysis Report',
    type: 'pdf',
    lastUpdated: '1 week ago'
  }, {
    id: 'b3',
    title: 'Competitor Research',
    type: 'url',
    lastUpdated: '3 days ago'
  }, {
    id: 'b4',
    title: 'User Research Findings',
    type: 'pdf',
    lastUpdated: '2 weeks ago'
  }, {
    id: 'b5',
    title: 'Business Requirements Document',
    type: 'pdf',
    lastUpdated: '4 days ago'
  }];
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
      {showAddSourceModal && <AddSourceModal sourceType={sourceType} onClose={() => setShowAddSourceModal(false)} />}
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
// Add Source Modal
const AddSourceModal: React.FC<{
  sourceType: 'technical' | 'business';
  onClose: () => void;
}> = ({
  sourceType,
  onClose
}) => {
  const [method, setMethod] = useState<'url' | 'file'>('url');
  const [url, setUrl] = useState('');
  const handleAddSource = () => {
    // Here you would handle adding the source
    console.log('Adding source:', {
      type: sourceType,
      method,
      url
    });
    onClose();
  };
  return <div className="fixed inset-0 bg-gray-500/50 dark:bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="relative p-6 rounded-md backdrop-blur-md w-full max-w-md
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
              Add {sourceType === 'technical' ? 'Technical' : 'Business'} Source
            </h3>
            <button onClick={onClose} className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-white transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>
          {/* Source Type Selection */}
          <div className="flex gap-3 mb-6">
            <button onClick={() => setMethod('url')} className={`flex-1 py-3 rounded-md flex items-center justify-center gap-2 transition-all ${method === 'url' ? 'bg-blue-900/30 border border-blue-500/50 text-blue-400' : 'bg-black/30 border border-gray-800 text-gray-400 hover:border-gray-700'}`}>
              <LinkIcon className="w-4 h-4" />
              <span>URL / Website</span>
            </button>
            <button onClick={() => setMethod('file')} className={`flex-1 py-3 rounded-md flex items-center justify-center gap-2 transition-all ${method === 'file' ? 'bg-pink-900/30 border border-pink-500/50 text-pink-400' : 'bg-black/30 border border-gray-800 text-gray-400 hover:border-gray-700'}`}>
              <Upload className="w-4 h-4" />
              <span>Upload File</span>
            </button>
          </div>
          {/* URL Input */}
          {method === 'url' && <div className="mb-6">
              <label className="block text-gray-300 mb-2">URL to Crawl</label>
              <input type="url" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://..." className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white rounded-md py-2 px-3 focus:outline-none focus:border-blue-400 focus:shadow-[0_0_10px_rgba(59,130,246,0.2)] transition-all duration-300" />
              <p className="text-gray-500 text-xs mt-2">
                The system will crawl this URL and extract relevant knowledge
              </p>
            </div>}
          {/* File Upload */}
          {method === 'file' && <div className="mb-6">
              <label className="block text-gray-300 mb-2">
                Upload Document
              </label>
              <div className="border border-dashed border-gray-700 rounded-md p-8 text-center hover:border-pink-500/50 transition-colors bg-black/30">
                <Upload className="w-8 h-8 text-gray-600 mx-auto mb-2" />
                <p className="text-gray-400">
                  Drag and drop your file here, or{' '}
                  <span className="text-pink-400">browse</span>
                </p>
                <p className="text-gray-500 text-xs mt-1">
                  Supports PDF, DOCX, MD, TXT up to 10MB
                </p>
              </div>
            </div>}
          {/* Action Buttons */}
          <div className="flex justify-end gap-3">
            <Button onClick={onClose} variant="ghost">
              Cancel
            </Button>
            <Button onClick={handleAddSource} variant="primary" accentColor="blue" className="shadow-lg shadow-blue-500/20">
              Add Source
            </Button>
          </div>
        </div>
      </div>
    </div>;
};