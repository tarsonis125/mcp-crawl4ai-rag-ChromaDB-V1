import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useStaggeredEntrance } from '../hooks/useStaggeredEntrance';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/project-tasks/Tabs';
import { DocsTab } from '../components/project-tasks/DocsTab';
import { FeaturesTab } from '../components/project-tasks/FeaturesTab';
import { DataTab } from '../components/project-tasks/DataTab';
import { TasksTab } from '../components/project-tasks/TasksTab';
import { Button } from '../components/ui/Button';
import { Task } from '../components/project-tasks/TasksTab';
import { ArrowLeft, ArrowRight, ChevronRight, ShoppingCart, Code, Briefcase, Layers, Plus, X } from 'lucide-react';
interface ProjectPageProps {
  className?: string;
  'data-id'?: string;
}
// Sample project data
const projects = [{
  id: '1',
  title: 'E-commerce Platform',
  description: 'Modern online shopping experience with React and Node.js',
  icon: <ShoppingCart className="w-5 h-5" />,
  color: 'cyan',
  progress: 65,
  updated: '2 days ago'
}, {
  id: '2',
  title: 'Banking Dashboard',
  description: 'Financial analytics and account management system',
  icon: <Briefcase className="w-5 h-5" />,
  color: 'purple',
  progress: 42,
  updated: '5 days ago'
}, {
  id: '3',
  title: 'Developer Portal',
  description: 'API documentation and developer resources hub',
  icon: <Code className="w-5 h-5" />,
  color: 'pink',
  progress: 78,
  updated: '1 day ago'
}, {
  id: '4',
  title: 'Content Management',
  description: 'Enterprise CMS with workflow and publishing tools',
  icon: <Layers className="w-5 h-5" />,
  color: 'blue',
  progress: 23,
  updated: '1 week ago'
}];
export function ProjectPage({
  className = '',
  'data-id': dataId
}: ProjectPageProps) {
  const [activeTab, setActiveTab] = useState('docs');
  const [selectedProject, setSelectedProject] = useState(projects[0]);
  const [showProjectDetails, setShowProjectDetails] = useState(true);
  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState(false);
  // Add the missing project selection handler
  const handleProjectSelect = (project: (typeof projects)[0]) => {
    setSelectedProject(project);
    setShowProjectDetails(true);
  };
  // Lift tasks state up from TasksTab
  const [tasks, setTasks] = useState<Task[]>([{
    id: '1',
    title: 'Implement user authentication',
    description: 'Create login and registration forms with validation...',
    status: 'backlog',
    assignee: {
      name: 'Alex Chen',
      avatar: 'https://randomuser.me/api/portraits/men/32.jpg'
    },
    feature: 'Authentication',
    featureColor: '#4338ca',
    priority: 'high'
  }
  // ... rest of the tasks array
  ]);
  // Add staggered entrance animations
  const {
    isVisible,
    containerVariants,
    itemVariants,
    titleVariants
  } = useStaggeredEntrance([1, 2, 3], 0.15);
  // Add animation for tab content
  const tabContentVariants = {
    hidden: {
      opacity: 0,
      y: 20
    },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.4,
        ease: 'easeOut'
      }
    },
    exit: {
      opacity: 0,
      y: -20,
      transition: {
        duration: 0.2
      }
    }
  };
  return <motion.div initial="hidden" animate={isVisible ? 'visible' : 'hidden'} variants={containerVariants} className={`max-w-full mx-auto ${className}`} data-id={dataId}>
      {/* Page Header with New Project Button */}
      <motion.div className="flex items-center justify-between mb-8" variants={itemVariants}>
        <motion.h1 className="text-3xl font-bold text-gray-800 dark:text-white" variants={titleVariants}>
          Projects
        </motion.h1>
        <Button onClick={() => setIsNewProjectModalOpen(true)} variant="primary" accentColor="purple" className="shadow-lg shadow-purple-500/20">
          <Plus className="w-4 h-4 mr-2 inline" />
          <span>New Project</span>
        </Button>
      </motion.div>
      {/* Project Cards - Horizontally Scrollable */}
      <motion.div className="relative mb-10" variants={itemVariants}>
        <div className="overflow-x-auto pb-4 hide-scrollbar">
          <div className="flex gap-4 min-w-max">
            {projects.map(project => <motion.div key={project.id} variants={itemVariants} onClick={() => handleProjectSelect(project)} className={`
                  relative p-4 rounded-md backdrop-blur-md w-72 cursor-pointer
                  bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30
                  border border-gray-200 dark:border-zinc-800/50
                  shadow-[0_10px_30px_-15px_rgba(0,0,0,0.1)] dark:shadow-[0_10px_30px_-15px_rgba(0,0,0,0.7)]
                  hover:shadow-[0_15px_40px_-15px_rgba(0,0,0,0.2)] dark:hover:shadow-[0_15px_40px_-15px_rgba(0,0,0,0.9)]
                  transition-all duration-300
                  ${selectedProject.id === project.id ? 'border-purple-300 dark:border-purple-500/30 translate-y-[-2px]' : 'hover:translate-y-[-2px]'}
                  ${selectedProject.id === project.id ? `
                      before:content-[""] before:absolute before:top-0 before:left-0 before:right-0 before:h-[2px] 
                      before:rounded-t-[4px] before:bg-purple-500 
                      before:shadow-[0_0_10px_2px_rgba(168,85,247,0.4)] dark:before:shadow-[0_0_20px_5px_rgba(168,85,247,0.7)]
                      after:content-[""] after:absolute after:top-0 after:left-0 after:right-0 after:h-16
                      after:bg-gradient-to-b after:from-purple-100 after:to-white dark:after:from-purple-500/20 dark:after:to-purple-500/5
                      after:rounded-t-md after:pointer-events-none
                    ` : ''}
                `}>
                <div className="relative z-10">
                  <div className="flex items-center gap-3 mb-3">
                    <div className={`p-2 rounded-md bg-${project.color}-500/10 text-${project.color}-500`}>
                      {project.icon}
                    </div>
                    <h3 className="text-gray-800 dark:text-white font-medium">
                      {project.title}
                    </h3>
                  </div>
                  <p className="text-gray-600 dark:text-gray-400 text-sm mb-4">
                    {project.description}
                  </p>
                  <div className="flex justify-between items-center text-xs text-gray-500 dark:text-gray-500">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-gray-200 dark:bg-gray-800 rounded-full overflow-hidden">
                        <div className={`h-full bg-${project.color}-500`} style={{
                      width: `${project.progress}%`
                    }}></div>
                      </div>
                      <span>{project.progress}%</span>
                    </div>
                    <span>Updated {project.updated}</span>
                  </div>
                </div>
              </motion.div>)}
          </div>
        </div>
        {/* Scroll indicators/buttons could be added here if needed */}
      </motion.div>
      {/* Project Details Section */}
      {showProjectDetails && <motion.div variants={itemVariants}>
          <div className="flex items-center gap-2 mb-6">
            <h2 className="text-2xl font-bold bg-gradient-to-r from-purple-400 via-fuchsia-500 to-purple-400 text-transparent bg-clip-text">
              {selectedProject.title}
            </h2>
            <ChevronRight className="w-5 h-5 text-gray-600 dark:text-gray-400" />
            <span className="text-gray-600 dark:text-gray-400 text-sm">
              Project Details
            </span>
          </div>
          <Tabs defaultValue="docs" value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList>
              <TabsTrigger value="docs" className="py-3 font-mono transition-all duration-300" color="blue">
                Docs
              </TabsTrigger>
              <TabsTrigger value="features" className="py-3 font-mono transition-all duration-300" color="purple">
                Features
              </TabsTrigger>
              <TabsTrigger value="data" className="py-3 font-mono transition-all duration-300" color="pink">
                Data
              </TabsTrigger>
              <TabsTrigger value="tasks" className="py-3 font-mono transition-all duration-300" color="orange">
                Tasks
              </TabsTrigger>
            </TabsList>
            {/* Add AnimatePresence for tab content transitions */}
            <AnimatePresence mode="wait">
              <motion.div key={activeTab} initial="hidden" animate="visible" exit="exit" variants={tabContentVariants}>
                {activeTab === 'docs' && <TabsContent value="docs" className="mt-0">
                    <DocsTab tasks={tasks} />
                  </TabsContent>}
                {activeTab === 'features' && <TabsContent value="features" className="mt-0">
                    <FeaturesTab />
                  </TabsContent>}
                {activeTab === 'data' && <TabsContent value="data" className="mt-0">
                    <DataTab />
                  </TabsContent>}
                {activeTab === 'tasks' && <TabsContent value="tasks" className="mt-0">
                    <TasksTab initialTasks={tasks} onTasksChange={setTasks} />
                  </TabsContent>}
              </motion.div>
            </AnimatePresence>
          </Tabs>
        </motion.div>}
      {/* New Project Modal */}
      {isNewProjectModalOpen && <div className="fixed inset-0 bg-black/50 dark:bg-black/80 flex items-center justify-center z-50 backdrop-blur-sm">
          <div className="relative p-6 rounded-md backdrop-blur-md w-full max-w-md
              bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30
              border border-gray-200 dark:border-zinc-800/50
              shadow-[0_10px_30px_-15px_rgba(0,0,0,0.1)] dark:shadow-[0_10px_30px_-15px_rgba(0,0,0,0.7)]
              before:content-[''] before:absolute before:top-0 before:left-0 before:right-0 before:h-[2px] 
              before:rounded-t-[4px] before:bg-purple-500 
              before:shadow-[0_0_10px_2px_rgba(168,85,247,0.4)] dark:before:shadow-[0_0_20px_5px_rgba(168,85,247,0.7)]
              after:content-[''] after:absolute after:top-0 after:left-0 after:right-0 after:h-16
              after:bg-gradient-to-b after:from-purple-100 after:to-white dark:after:from-purple-500/20 dark:after:to-purple-500/5
              after:rounded-t-md after:pointer-events-none">
            <div className="relative z-10">
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-xl font-bold bg-gradient-to-r from-purple-400 to-fuchsia-500 text-transparent bg-clip-text">
                  Create New Project
                </h3>
                <button onClick={() => setIsNewProjectModalOpen(false)} className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-white transition-colors">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 mb-1">
                    Project Name
                  </label>
                  <input type="text" placeholder="Enter project name..." className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white rounded-md py-2 px-3 focus:outline-none focus:border-purple-400 focus:shadow-[0_0_10px_rgba(168,85,247,0.2)] transition-all duration-300" />
                </div>
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 mb-1">
                    Description
                  </label>
                  <textarea placeholder="Enter project description..." rows={4} className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white rounded-md py-2 px-3 focus:outline-none focus:border-purple-400 focus:shadow-[0_0_10px_rgba(168,85,247,0.2)] transition-all duration-300" />
                </div>
              </div>
              <div className="flex justify-end gap-3 mt-6">
                <Button onClick={() => setIsNewProjectModalOpen(false)} variant="ghost">
                  Cancel
                </Button>
                <Button onClick={() => {
              // Handle project creation
              setIsNewProjectModalOpen(false);
            }} variant="primary" accentColor="purple" className="shadow-lg shadow-purple-500/20">
                  Create Project
                </Button>
              </div>
            </div>
          </div>
        </div>}
    </motion.div>;
}