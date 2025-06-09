import React, { useState, useEffect } from 'react';
import { X, Clock, RotateCcw, Eye, Calendar, User, FileText } from 'lucide-react';
import projectService from '../../services/projectService';

interface Version {
  id: string;
  version_number: number;
  change_summary: string;
  change_type: string;
  created_by: string;
  created_at: string;
  content: any;
  document_id?: string;
}

interface VersionHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  documentId?: string;
  fieldName?: string;
  onRestore?: () => void;
}

export const VersionHistoryModal: React.FC<VersionHistoryModalProps> = ({
  isOpen,
  onClose,
  projectId,
  documentId,
  fieldName = 'docs',
  onRestore
}) => {
  const [versions, setVersions] = useState<Version[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState<any>(null);
  const [previewVersion, setPreviewVersion] = useState<number | null>(null);
  const [restoring, setRestoring] = useState<number | null>(null);

  useEffect(() => {
    if (isOpen && projectId) {
      loadVersionHistory();
    }
  }, [isOpen, projectId, fieldName]);

  const loadVersionHistory = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Use projectService instead of MCP tool calling
      const versionData = await projectService.getDocumentVersionHistory(projectId, fieldName);
      setVersions(versionData || []);
    } catch (error) {
      console.error('Error loading version history:', error);
      setError('Failed to load version history');
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async (versionNumber: number) => {
    try {
      setPreviewVersion(versionNumber);
      
      // Use projectService to get version content
      const contentData = await projectService.getVersionContent(projectId, versionNumber, fieldName);
      setPreviewContent(contentData.content);
    } catch (error) {
      console.error('Error loading version content:', error);
      setError('Failed to load version content');
    }
  };

  const handleRestore = async (versionNumber: number) => {
    if (!confirm(`Are you sure you want to restore to version ${versionNumber}? This will create a new version with the restored content.`)) {
      return;
    }

    setRestoring(versionNumber);
    setError(null);

    try {
      // Use projectService to restore version
      await projectService.restoreDocumentVersion(projectId, versionNumber, fieldName);
      
      // Refresh version history
      await loadVersionHistory();
      
      // Call onRestore callback if provided
      if (onRestore) {
        onRestore();
      }
      
      // Show success message (you could use a toast here)
      alert(`Successfully restored to version ${versionNumber}`);
    } catch (error) {
      console.error('Error restoring version:', error);
      setError('Failed to restore version');
    } finally {
      setRestoring(null);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const getChangeTypeIcon = (changeType: string) => {
    switch (changeType) {
      case 'create':
        return <FileText className="w-4 h-4 text-green-500" />;
      case 'update':
        return <Clock className="w-4 h-4 text-blue-500" />;
      case 'delete':
        return <X className="w-4 h-4 text-red-500" />;
      case 'restore':
        return <RotateCcw className="w-4 h-4 text-purple-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl h-3/4 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Clock className="w-5 h-5" />
            Version History - {fieldName}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Version List */}
          <div className="w-1/2 border-r border-gray-200 dark:border-gray-700 overflow-y-auto">
            <div className="p-4">
              <h3 className="font-medium text-gray-900 dark:text-white mb-4">Versions</h3>
              
              {loading && (
                <div className="text-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
                  <p className="text-gray-500 mt-2">Loading versions...</p>
                </div>
              )}

              {error && (
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md p-3 mb-4">
                  <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>
                </div>
              )}

              {!loading && versions.length === 0 && (
                <div className="text-center py-8">
                  <Clock className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-500">No versions found</p>
                </div>
              )}

              <div className="space-y-3">
                {versions.map((version) => (
                  <div
                    key={version.id}
                    className={`border rounded-lg p-3 cursor-pointer transition-colors ${
                      previewVersion === version.version_number
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                        : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                    }`}
                    onClick={() => handlePreview(version.version_number)}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        {getChangeTypeIcon(version.change_type)}
                        <span className="font-medium text-gray-900 dark:text-white">
                          Version {version.version_number}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handlePreview(version.version_number);
                          }}
                          className="text-blue-500 hover:text-blue-700 p-1"
                          title="Preview"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRestore(version.version_number);
                          }}
                          disabled={restoring === version.version_number}
                          className="text-green-500 hover:text-green-700 p-1 disabled:opacity-50"
                          title="Restore"
                        >
                          {restoring === version.version_number ? (
                            <div className="animate-spin w-4 h-4 border-2 border-green-500 border-t-transparent rounded-full" />
                          ) : (
                            <RotateCcw className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                    </div>
                    
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                      {version.change_summary}
                    </p>
                    
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      <div className="flex items-center gap-1">
                        <User className="w-3 h-3" />
                        {version.created_by}
                      </div>
                      <div className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {formatDate(version.created_at)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Preview Panel */}
          <div className="w-1/2 overflow-y-auto">
            <div className="p-4">
              <h3 className="font-medium text-gray-900 dark:text-white mb-4">Preview</h3>
              
              {previewVersion === null ? (
                <div className="text-center py-8">
                  <Eye className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-500">Select a version to preview</p>
                </div>
              ) : (
                <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                  <div className="mb-4">
                    <h4 className="font-medium text-gray-900 dark:text-white">
                      Version {previewVersion} Content
                    </h4>
                  </div>
                  
                  <pre className="bg-white dark:bg-gray-800 rounded border p-3 text-sm overflow-x-auto whitespace-pre-wrap">
                    {previewContent ? JSON.stringify(previewContent, null, 2) : 'Loading...'}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 dark:border-gray-700 p-4">
          <div className="flex justify-end gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}; 