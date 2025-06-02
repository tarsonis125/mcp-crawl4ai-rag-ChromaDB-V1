import React, { useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './Tabs';
import { DocsTab } from './DocsTab';
import { FeaturesTab } from './FeaturesTab';
import { DataTab } from './DataTab';
import { TasksTab } from './TasksTab';
interface ProjectPageProps {
  className?: string;
  'data-id'?: string;
}
export function ProjectPage({
  className = '',
  'data-id': dataId
}: ProjectPageProps) {
  const [activeTab, setActiveTab] = useState('docs');
  return <div className={`max-w-full mx-auto ${className}`} data-id={dataId}>
      <div className="flex items-center gap-4 mb-6">
        <Link to="/dashboard" className="text-gray-400 hover:text-cyan-400 transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 via-fuchsia-500 to-cyan-400 text-transparent bg-clip-text">
          E-commerce Platform
        </h1>
      </div>
      <Tabs defaultValue="docs" value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid grid-cols-4 mb-6 bg-black/50 backdrop-blur-lg border border-gray-800 rounded-lg overflow-hidden">
          <TabsTrigger value="docs" className="py-3 font-mono transition-all duration-300">
            Docs
          </TabsTrigger>
          <TabsTrigger value="features" className="py-3 font-mono transition-all duration-300">
            Features
          </TabsTrigger>
          <TabsTrigger value="data" className="py-3 font-mono transition-all duration-300">
            Data
          </TabsTrigger>
          <TabsTrigger value="tasks" className="py-3 font-mono transition-all duration-300">
            Tasks
          </TabsTrigger>
        </TabsList>
        <TabsContent value="docs" className="mt-16">
          <DocsTab />
        </TabsContent>
        <TabsContent value="features" className="mt-6">
          <FeaturesTab />
        </TabsContent>
        <TabsContent value="data" className="mt-6">
          <DataTab />
        </TabsContent>
        <TabsContent value="tasks" className="mt-6">
          <TasksTab />
        </TabsContent>
      </Tabs>
    </div>;
}