import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ChevronDown, 
  ChevronUp, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  Globe, 
  FileText,
  RotateCcw
} from 'lucide-react';
import { Card } from './ui/Card';
import { Button } from './ui/Button';
import { Badge } from './ui/Badge';
import { CrawlProgressData, crawlProgressService } from '../services/crawlProgressService';

interface CrawlingProgressCardProps {
  progressData: CrawlProgressData;
  onComplete: (data: CrawlProgressData) => void;
  onError: (error: string) => void;
  onProgress?: (data: CrawlProgressData) => void;
  onRetry?: () => void;
}

export const CrawlingProgressCard: React.FC<CrawlingProgressCardProps> = ({
  progressData: initialData,
  onComplete,
  onError,
  onProgress,
  onRetry
}) => {
  const [progressData, setProgressData] = useState<CrawlProgressData>(initialData);
  const [showLogs, setShowLogs] = useState(false);

  // Update local state when props change
  useEffect(() => {
    setProgressData(initialData);
  }, [initialData]);

  // React to progress data changes from parent component (no WebSocket setup here)
  // The KnowledgeBasePage handles WebSocket connections and passes updated data via props
  useEffect(() => {
    // Simply update local state when props change - WebSocket handled by parent
    setProgressData(initialData);
  }, [initialData]);

  const getStatusDisplay = () => {
    switch (progressData.status) {
      case 'starting':
        return {
          text: 'Starting crawl...',
          color: 'blue' as const,
          icon: <Clock className="w-4 h-4" />
        };
      case 'crawling':
        return {
          text: 'Crawling in progress...',
          color: 'blue' as const,
          icon: <Globe className="w-4 h-4 animate-spin" />
        };
      case 'completed':
        return {
          text: 'Crawling completed!',
          color: 'green' as const,
          icon: <CheckCircle className="w-4 h-4" />
        };
      case 'error':
        return {
          text: 'Crawling failed',
          color: 'pink' as const,
          icon: <AlertTriangle className="w-4 h-4" />
        };
      default:
        return {
          text: 'Unknown status',
          color: 'purple' as const,
          icon: <Clock className="w-4 h-4" />
        };
    }
  };

  const status = getStatusDisplay();

  const formatNumber = (num: number): string => {
    return num.toLocaleString();
  };

  return (
    <Card accentColor={status.color} className="relative overflow-hidden">
      {/* Status Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className={`p-2 rounded-md ${
          status.color === 'blue' ? 'bg-blue-100 dark:bg-blue-500/10 text-blue-600 dark:text-blue-400' :
          status.color === 'green' ? 'bg-green-100 dark:bg-green-500/10 text-green-600 dark:text-green-400' :
          status.color === 'pink' ? 'bg-pink-100 dark:bg-pink-500/10 text-pink-600 dark:text-pink-400' :
          status.color === 'purple' ? 'bg-purple-100 dark:bg-purple-500/10 text-purple-600 dark:text-purple-400' :
          'bg-gray-100 dark:bg-gray-500/10 text-gray-600 dark:text-gray-400'
        }`}>
          {status.icon}
        </div>
        <div className="flex-1">
          <h3 className="font-medium text-gray-800 dark:text-white">
            {status.text}
          </h3>
          {progressData.currentUrl && (
            <p className="text-sm text-gray-500 dark:text-zinc-400 truncate">
              {progressData.currentUrl}
            </p>
          )}
        </div>
        <Badge color={status.color === 'purple' ? 'gray' : status.color}>
          {progressData.percentage}%
        </Badge>
      </div>

      {/* Progress Bar */}
      {progressData.status !== 'completed' && (
        <div className="mb-4">
          <div className="w-full bg-gray-200 dark:bg-zinc-800 rounded-full h-2">
            <motion.div
              className={`h-2 rounded-full ${
                status.color === 'blue' ? 'bg-blue-500' :
                status.color === 'green' ? 'bg-green-500' :
                status.color === 'pink' ? 'bg-pink-500' :
                status.color === 'purple' ? 'bg-purple-500' :
                'bg-gray-500'
              }`}
              initial={{ width: 0 }}
              animate={{ width: `${progressData.percentage}%` }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
            />
          </div>
          {progressData.eta && (
            <p className="text-xs text-gray-500 dark:text-zinc-400 mt-1">
              {progressData.eta}
            </p>
          )}
        </div>
      )}

      {/* Progress Details */}
      <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
        {progressData.totalPages && progressData.processedPages !== undefined && (
          <div>
            <span className="text-gray-500 dark:text-zinc-400">Pages:</span>
            <span className="ml-2 font-medium text-gray-800 dark:text-white">
              {progressData.processedPages} of {progressData.totalPages} pages processed
            </span>
          </div>
        )}
        
        {progressData.status === 'completed' && (
          <>
            {progressData.chunksStored && (
              <div>
                <span className="text-gray-500 dark:text-zinc-400">Chunks:</span>
                <span className="ml-2 font-medium text-gray-800 dark:text-white">
                  {formatNumber(progressData.chunksStored)} chunks stored
                </span>
              </div>
            )}
            {progressData.wordCount && (
              <div>
                <span className="text-gray-500 dark:text-zinc-400">Words:</span>
                <span className="ml-2 font-medium text-gray-800 dark:text-white">
                  {formatNumber(progressData.wordCount)} words processed
                </span>
              </div>
            )}
            {progressData.duration && (
              <div className="col-span-2">
                <span className="text-gray-500 dark:text-zinc-400">Duration:</span>
                <span className="ml-2 font-medium text-gray-800 dark:text-white">
                  {progressData.duration}
                </span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Error Message */}
      {progressData.status === 'error' && progressData.error && (
        <div className="mb-4 p-3 bg-pink-50 dark:bg-pink-500/10 border border-pink-200 dark:border-pink-500/20 rounded-md">
          <p className="text-pink-700 dark:text-pink-400 text-sm">
            {progressData.error}
          </p>
        </div>
      )}

      {/* Console Logs */}
      {progressData.logs && progressData.logs.length > 0 && (
        <div className="border-t border-gray-200 dark:border-zinc-800 pt-4">
          <button
            onClick={() => setShowLogs(!showLogs)}
            className="flex items-center gap-2 text-sm text-gray-600 dark:text-zinc-400 hover:text-gray-800 dark:hover:text-white transition-colors mb-2"
          >
            <FileText className="w-4 h-4" />
            <span>View Console Output</span>
            {showLogs ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          
          <AnimatePresence>
            {showLogs && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="bg-gray-900 dark:bg-black rounded-md p-3 max-h-32 overflow-y-auto">
                  <div className="space-y-1 font-mono text-xs">
                    {progressData.logs.map((log, index) => (
                      <div key={index} className="text-green-400">
                        {log}
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Action Buttons */}
      {progressData.status === 'error' && onRetry && (
        <div className="flex justify-end mt-4 pt-4 border-t border-gray-200 dark:border-zinc-800">
          <Button 
            onClick={onRetry}
            variant="primary" 
            accentColor="blue"
            className="text-sm"
          >
            <RotateCcw className="w-4 h-4 mr-2" />
            Retry
          </Button>
        </div>
      )}
    </Card>
  );
}; 