import React from 'react';
import { KnowledgeItem } from '../../services/knowledgeBaseService';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Link as LinkIcon, Upload, Trash2, RefreshCw, X } from 'lucide-react';
import { format } from 'date-fns';

interface KnowledgeTableProps {
  items: KnowledgeItem[];
  onDelete: (sourceId: string) => void;
}

export const KnowledgeTable: React.FC<KnowledgeTableProps> = ({ items, onDelete }) => {
  const statusColorMap = {
    active: 'green',
    processing: 'blue',
    error: 'pink'
  };

  // Get frequency display - based on update_frequency days
  const getFrequencyDisplay = (frequency?: number) => {
    if (!frequency || frequency === 0) {
      return { icon: <X className="w-3 h-3" />, text: 'Never', color: 'text-gray-500 dark:text-zinc-500' };
    } else if (frequency === 1) {
      return { icon: <RefreshCw className="w-3 h-3" />, text: 'Daily', color: 'text-green-500' };
    } else if (frequency === 7) {
      return { icon: <RefreshCw className="w-3 h-3" />, text: 'Weekly', color: 'text-blue-500' };
    } else if (frequency === 30) {
      return { icon: <RefreshCw className="w-3 h-3" />, text: 'Monthly', color: 'text-purple-500' };
    } else {
      return { icon: <RefreshCw className="w-3 h-3" />, text: `Every ${frequency} days`, color: 'text-gray-500 dark:text-zinc-500' };
    }
  };

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-zinc-700">
        <thead className="bg-gray-50 dark:bg-zinc-900/50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-zinc-400 uppercase tracking-wider">
              Title
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-zinc-400 uppercase tracking-wider">
              Type
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-zinc-400 uppercase tracking-wider">
              Tags
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-zinc-400 uppercase tracking-wider">
              Chunks
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-zinc-400 uppercase tracking-wider">
              Updated
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-zinc-400 uppercase tracking-wider">
              Frequency
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-zinc-400 uppercase tracking-wider">
              Status
            </th>
            <th className="relative px-6 py-3">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody className="bg-white dark:bg-zinc-900 divide-y divide-gray-200 dark:divide-zinc-700">
          {items.map((item) => {
            const frequencyDisplay = getFrequencyDisplay(item.metadata.update_frequency);
            return (
              <tr key={item.id} className="hover:bg-gray-50 dark:hover:bg-zinc-800/50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center gap-2">
                    {item.metadata.source_type === 'url' ? (
                      <LinkIcon className="w-4 h-4 text-blue-500" />
                    ) : (
                      <Upload className="w-4 h-4 text-pink-500" />
                    )}
                    <div className="text-sm font-medium text-gray-900 dark:text-white">
                      {item.title}
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-zinc-400">
                  <Badge color={item.metadata.knowledge_type === 'technical' ? 'blue' : 'purple'}>
                    {item.metadata.knowledge_type}
                  </Badge>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex flex-wrap gap-1">
                                         {item.metadata.tags?.slice(0, 2).map(tag => (
                       <Badge key={tag} color="purple" variant="outline">
                         {tag}
                       </Badge>
                     ))}
                     {(item.metadata.tags?.length || 0) > 2 && (
                       <Badge color="gray" variant="outline">
                         +{(item.metadata.tags?.length || 0) - 2}
                       </Badge>
                     )}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-zinc-400">
                  {item.metadata.chunks_count || 0}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-zinc-400">
                  {format(new Date(item.updated_at), 'MMM dd, yyyy')}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className={`flex items-center gap-1 ${frequencyDisplay.color}`}>
                    {frequencyDisplay.icon}
                    <span className="text-sm">{frequencyDisplay.text}</span>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <Badge color={statusColorMap[item.metadata.status || 'active'] as any}>
                    {(item.metadata.status || 'active').charAt(0).toUpperCase() + (item.metadata.status || 'active').slice(1)}
                  </Badge>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <div className="flex justify-end gap-2">
                    <button onClick={() => onDelete(item.source_id)} className="p-2 text-gray-500 hover:text-red-500" title="Delete">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
