import React from 'react';
import { KnowledgeItem } from '../../services/knowledgeBaseService';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Link as LinkIcon, Upload, TestTube, Trash2 } from 'lucide-react';
import { format } from 'date-fns';

interface KnowledgeTableProps {
  items: KnowledgeItem[];
  onDelete: (sourceId: string) => void;
  onTest: (item: KnowledgeItem) => void;
}

export const KnowledgeTable: React.FC<KnowledgeTableProps> = ({ items, onDelete, onTest }) => {
  const statusColorMap = {
    active: 'green',
    processing: 'blue',
    error: 'pink',
  };

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-zinc-800">
        <thead className="bg-gray-50 dark:bg-zinc-900">
          <tr>
            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-zinc-400 uppercase tracking-wider">
              Title
            </th>
            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-zinc-400 uppercase tracking-wider">
              Type
            </th>
            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-zinc-400 uppercase tracking-wider">
              Source
            </th>
            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-zinc-400 uppercase tracking-wider">
              Tags
            </th>
            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-zinc-400 uppercase tracking-wider">
              Updated
            </th>
            <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-zinc-400 uppercase tracking-wider">
              Status
            </th>
            <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-zinc-400 uppercase tracking-wider">
              Actions
            </th>
          </tr>
        </thead>
        <tbody className="bg-white dark:bg-black divide-y divide-gray-200 dark:divide-zinc-800">
          {items.length === 0 ? (
            <tr>
              <td colSpan={7} className="px-6 py-4 whitespace-nowrap text-center text-gray-500 dark:text-zinc-400">
                No knowledge items found.
              </td>
            </tr>
          ) : (
            items.map((item) => (
              <tr key={item.id} className="hover:bg-gray-50 dark:hover:bg-zinc-900 transition-colors">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <div className="text-sm font-medium text-gray-900 dark:text-white">
                      {item.title}
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <Badge color={item.metadata.knowledge_type === 'technical' ? 'blue' : 'purple'}>
                    {item.metadata.knowledge_type}
                  </Badge>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-zinc-400">
                  <div className="flex items-center gap-1">
                    {item.metadata.source_type === 'url' ? <LinkIcon className="w-4 h-4 text-blue-500" /> : <Upload className="w-4 h-4 text-pink-500" />}
                    {item.metadata.source_type === 'url' ? item.url : item.metadata.file_name || 'Uploaded File'}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex flex-wrap gap-1">
                    {item.metadata.tags?.map(tag => (
                      <Badge key={tag} color="purple" variant="outline">
                        {tag}
                      </Badge>
                    )) || null}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-zinc-400">
                  {format(new Date(item.updated_at), 'MMM dd, yyyy')}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <Badge color={statusColorMap[item.metadata.status || 'active'] as any}>
                    {(item.metadata.status || 'active').charAt(0).toUpperCase() + (item.metadata.status || 'active').slice(1)}
                  </Badge>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <div className="flex justify-end gap-2">
                    <button onClick={() => onTest(item)} className="p-2 text-gray-500 hover:text-blue-500" title="Test with Query">
                      <TestTube className="w-4 h-4" />
                    </button>
                    <button onClick={() => onDelete(item.source_id)} className="p-2 text-gray-500 hover:text-red-500" title="Delete">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
};
