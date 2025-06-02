import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useStaggeredEntrance } from '../hooks/useStaggeredEntrance';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/project-tasks/Tabs';
import { DocsTab } from '../components/project-tasks/DocsTab';
import { FeaturesTab } from '../components/project-tasks/FeaturesTab';
import { DataTab } from '../components/project-tasks/DataTab';
import { TasksTab } from '../components/project-tasks/TasksTab';
import { Button } from '../components/ui/Button';
import { ChevronRight, ShoppingCart, Code, Briefcase, Layers, Plus, X, AlertCircle, Loader2, Heart, BarChart3 } from 'lucide-react';

// Import our service layer and types
import { projectService } from '../services/projectService';
import type { Project, CreateProjectRequest } from '../types/project';
import type { Task } from '../components/project-tasks/TasksTab';

interface ProjectPageProps {
  className?: string;
  'data-id'?: string;
}

// Icon mapping for projects (since database stores icon names as strings)
const getProjectIcon = (iconName?: string) => {
  const iconMap = {
    'ShoppingCart': <ShoppingCart className="w-5 h-5" />,
    'Briefcase': <Briefcase className="w-5 h-5" />,
    'Code': <Code className="w-5 h-5" />,
    'Layers': <Layers className="w-5 h-5" />,
    'BarChart': <BarChart3 className="w-5 h-5" />,
    'Heart': <Heart className="w-5 h-5" />,
  };
  return iconMap[iconName as keyof typeof iconMap] || <Briefcase className="w-5 h-5" />;
};

export function ProjectPage({
  className = '',
  'data-id': dataId
}: ProjectPageProps) {
  // State management for real data
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoadingProjects, setIsLoadingProjects] = useState(true);
  const [isLoadingTasks, setIsLoadingTasks] = useState(false);
  const [projectsError, setProjectsError] = useState<string | null>(null);
  const [tasksError, setTasksError] = useState<string | null>(null);
  
  // UI state
  const [activeTab, setActiveTab] = useState('docs');
  const [showProjectDetails, setShowProjectDetails] = useState(false);
  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState(false);
  
  // New project form state
  const [newProjectForm, setNewProjectForm] = useState({
    title: '',
    description: '',
    color: 'blue' as const
  });
  const [isCreatingProject, setIsCreatingProject] = useState(false);

  // Load projects on component mount
  useEffect(() => {
    loadProjects();
  }, []);

  // Load tasks when project is selected
  useEffect(() => {
    if (selectedProject) {
      loadTasksForProject(selectedProject.id);
    }
  }, [selectedProject]);

  const loadProjects = async () => {
    try {
      setIsLoadingProjects(true);
      setProjectsError(null);
      
      const projectsData = await projectService.listProjects();
      setProjects(projectsData);
      
      // Auto-select first project if none selected
      if (projectsData.length > 0 && !selectedProject) {
        setSelectedProject(projectsData[0]);
        setShowProjectDetails(true);
      }
    } catch (error) {
      console.error('Failed to load projects:', error);
      setProjectsError(error instanceof Error ? error.message : 'Failed to load projects');
    } finally {
      setIsLoadingProjects(false);
    }
  };

  const loadTasksForProject = async (projectId: string) => {
    try {
      setIsLoadingTasks(true);
      setTasksError(null);
      
      const tasksData = await projectService.getTasksByProject(projectId);
      
             // Convert backend tasks to UI format
       const uiTasks: Task[] = tasksData.map(task => ({
         id: task.id,
         title: task.title,
         description: task.description,
         status: (task.uiStatus || 'backlog') as Task['status'],
         assignee: task.assignee || {
           name: 'Unassigned',
           avatar: 'https://randomuser.me/api/portraits/lego/1.jpg'
         },
         feature: task.feature || 'General',
         featureColor: task.featureColor || '#6366f1',
         priority: (task.priority || 'medium') as Task['priority']
       }));
       
       setTasks(uiTasks);
    } catch (error) {
      console.error('Failed to load tasks:', error);
      setTasksError(error instanceof Error ? error.message : 'Failed to load tasks');
    } finally {
      setIsLoadingTasks(false);
    }
  };

  const handleProjectSelect = (project: Project) => {
    setSelectedProject(project);
    setShowProjectDetails(true);
  };

  const handleCreateProject = async () => {
    if (!newProjectForm.title.trim()) {
      return;
    }

    try {
      setIsCreatingProject(true);
      
      const projectData: CreateProjectRequest = {
        title: newProjectForm.title,
        description: newProjectForm.description,
        color: newProjectForm.color,
        icon: 'Briefcase', // Default icon
        prd: {
          overview: newProjectForm.description,
          status: 'planning'
        },
        docs: [],
        features: [],
        data: []
      };

      const newProject = await projectService.createProject(projectData);
      
      // Add to local state
      setProjects((prev) => [...prev, newProject]);
      
      // Select the new project
      setSelectedProject(newProject);
      setShowProjectDetails(true);
      
      // Reset form and close modal
      setNewProjectForm({ title: '', description: '', color: 'blue' });
      setIsNewProjectModalOpen(false);
      
      console.log('✅ Project created successfully:', newProject);
    } catch (error) {
      console.error('Failed to create project:', error);
      // TODO: Add toast notification for error
    } finally {
      setIsCreatingProject(false);
    }
  };

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

  return (
    <motion.div 
      initial="hidden" 
      animate={isVisible ? 'visible' : 'hidden'} 
      variants={containerVariants} 
      className={`max-w-full mx-auto ${className}`} 
      data-id={dataId}
    >
      {/* Page Header with New Project Button */}
      <motion.div className="flex items-center justify-between mb-8" variants={itemVariants}>
        <motion.h1 className="text-3xl font-bold text-gray-800 dark:text-white" variants={titleVariants}>
          Projects
        </motion.h1>
        <Button 
          onClick={() => setIsNewProjectModalOpen(true)} 
          variant="primary" 
          accentColor="purple" 
          className="shadow-lg shadow-purple-500/20"
        >
          <Plus className="w-4 h-4 mr-2 inline" />
          <span>New Project</span>
        </Button>
      </motion.div>

      {/* Projects Loading/Error States */}
      {isLoadingProjects && (
        <motion.div variants={itemVariants} className="mb-10">
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <Loader2 className="w-8 h-8 text-purple-500 mx-auto mb-4 animate-spin" />
              <p className="text-gray-600 dark:text-gray-400">Loading your projects...</p>
            </div>
          </div>
        </motion.div>
      )}

      {projectsError && (
        <motion.div variants={itemVariants} className="mb-10">
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <AlertCircle className="w-8 h-8 text-red-500 mx-auto mb-4" />
              <p className="text-red-600 dark:text-red-400 mb-4">{projectsError}</p>
              <Button onClick={loadProjects} variant="primary" accentColor="purple">
                Try Again
              </Button>
            </div>
          </div>
        </motion.div>
      )}

      {/* Project Cards - Horizontally Scrollable */}
      {!isLoadingProjects && !projectsError && (
        <motion.div className="relative mb-10" variants={itemVariants}>
          <div className="overflow-x-auto pb-4 hide-scrollbar">
            <div className="flex gap-4 min-w-max">
              {projects.map(project => (
                <motion.div 
                  key={project.id} 
                  variants={itemVariants} 
                  onClick={() => handleProjectSelect(project)} 
                  className={`
                    relative p-4 rounded-md backdrop-blur-md w-72 cursor-pointer
                    bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30
                    border border-gray-200 dark:border-zinc-800/50
                    shadow-[0_10px_30px_-15px_rgba(0,0,0,0.1)] dark:shadow-[0_10px_30px_-15px_rgba(0,0,0,0.7)]
                    hover:shadow-[0_15px_40px_-15px_rgba(0,0,0,0.2)] dark:hover:shadow-[0_15px_40px_-15px_rgba(0,0,0,0.9)]
                    transition-all duration-300
                    ${selectedProject?.id === project.id ? 'border-purple-300 dark:border-purple-500/30 translate-y-[-2px]' : 'hover:translate-y-[-2px]'}
                    ${selectedProject?.id === project.id ? `
                        before:content-[""] before:absolute before:top-0 before:left-0 before:right-0 before:h-[2px] 
                        before:rounded-t-[4px] before:bg-purple-500 
                        before:shadow-[0_0_10px_2px_rgba(168,85,247,0.4)] dark:before:shadow-[0_0_20px_5px_rgba(168,85,247,0.7)]
                        after:content-[""] after:absolute after:top-0 after:left-0 after:right-0 after:h-16
                        after:bg-gradient-to-b after:from-purple-100 after:to-white dark:after:from-purple-500/20 dark:after:to-purple-500/5
                        after:rounded-t-md after:pointer-events-none
                      ` : ''}
                  `}
                >
                  <div className="relative z-10">
                    <div className="flex items-center gap-3 mb-3">
                      <div className={`p-2 rounded-md bg-${project.color || 'blue'}-500/10 text-${project.color || 'blue'}-500`}>
                        {getProjectIcon(project.icon)}
                      </div>
                      <h3 className="text-gray-800 dark:text-white font-medium">
                        {project.title}
                      </h3>
                    </div>
                    <p className="text-gray-600 dark:text-gray-400 text-sm mb-4">
                      {project.description || 'No description available'}
                    </p>
                    <div className="flex justify-between items-center text-xs text-gray-500 dark:text-gray-500">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 bg-gray-200 dark:bg-gray-800 rounded-full overflow-hidden">
                          <div 
                            className={`h-full bg-${project.color || 'blue'}-500`} 
                            style={{ width: `${project.progress || 0}%` }}
                          />
                        </div>
                        <span>{project.progress || 0}%</span>
                      </div>
                      <span>Updated {project.updated || 'recently'}</span>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </motion.div>
      )}

      {/* Project Details Section */}
      {showProjectDetails && selectedProject && (
        <motion.div variants={itemVariants}>
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
              <motion.div 
                key={activeTab} 
                initial="hidden" 
                animate="visible" 
                exit="exit" 
                variants={tabContentVariants}
              >
                {activeTab === 'docs' && (
                  <TabsContent value="docs" className="mt-0">
                    <DocsTab tasks={tasks} />
                  </TabsContent>
                )}
                {activeTab === 'features' && (
                  <TabsContent value="features" className="mt-0">
                    <FeaturesTab />
                  </TabsContent>
                )}
                {activeTab === 'data' && (
                  <TabsContent value="data" className="mt-0">
                    <DataTab />
                  </TabsContent>
                )}
                {activeTab === 'tasks' && (
                  <TabsContent value="tasks" className="mt-0">
                    {isLoadingTasks ? (
                      <div className="flex items-center justify-center py-12">
                        <div className="text-center">
                          <Loader2 className="w-6 h-6 text-orange-500 mx-auto mb-4 animate-spin" />
                          <p className="text-gray-600 dark:text-gray-400">Loading tasks...</p>
                        </div>
                      </div>
                    ) : tasksError ? (
                      <div className="flex items-center justify-center py-12">
                        <div className="text-center">
                          <AlertCircle className="w-6 h-6 text-red-500 mx-auto mb-4" />
                          <p className="text-red-600 dark:text-red-400 mb-4">{tasksError}</p>
                                                     <Button 
                             onClick={() => loadTasksForProject(selectedProject.id)} 
                             variant="primary" 
                             accentColor="purple"
                           >
                            Retry
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <TasksTab initialTasks={tasks} onTasksChange={setTasks} />
                    )}
                  </TabsContent>
                )}
              </motion.div>
            </AnimatePresence>
          </Tabs>
        </motion.div>
      )}

      {/* New Project Modal */}
      {isNewProjectModalOpen && (
        <div className="fixed inset-0 bg-black/50 dark:bg-black/80 flex items-center justify-center z-50 backdrop-blur-sm">
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
                <button 
                  onClick={() => setIsNewProjectModalOpen(false)} 
                  className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-white transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 mb-1">
                    Project Name
                  </label>
                  <input 
                    type="text" 
                    placeholder="Enter project name..." 
                    value={newProjectForm.title}
                    onChange={(e) => setNewProjectForm((prev) => ({ ...prev, title: e.target.value }))}
                    className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white rounded-md py-2 px-3 focus:outline-none focus:border-purple-400 focus:shadow-[0_0_10px_rgba(168,85,247,0.2)] transition-all duration-300" 
                  />
                </div>
                <div>
                  <label className="block text-gray-700 dark:text-gray-300 mb-1">
                    Description
                  </label>
                  <textarea 
                    placeholder="Enter project description..." 
                    rows={4} 
                    value={newProjectForm.description}
                    onChange={(e) => setNewProjectForm((prev) => ({ ...prev, description: e.target.value }))}
                    className="w-full bg-white/50 dark:bg-black/70 border border-gray-300 dark:border-gray-700 text-gray-900 dark:text-white rounded-md py-2 px-3 focus:outline-none focus:border-purple-400 focus:shadow-[0_0_10px_rgba(168,85,247,0.2)] transition-all duration-300" 
                  />
                </div>
              </div>
              
              <div className="flex justify-end gap-3 mt-6">
                <Button 
                  onClick={() => setIsNewProjectModalOpen(false)} 
                  variant="ghost"
                  disabled={isCreatingProject}
                >
                  Cancel
                </Button>
                <Button 
                  onClick={handleCreateProject} 
                  variant="primary" 
                  accentColor="purple" 
                  className="shadow-lg shadow-purple-500/20"
                  disabled={isCreatingProject || !newProjectForm.title.trim()}
                >
                  {isCreatingProject ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    'Create Project'
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </motion.div>
  );
}