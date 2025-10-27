'use client';

import { useState } from 'react';
import { ADR } from '@/types/api';
import { ADRModal } from './ADRModal';
import { DeleteConfirmationModal } from './DeleteConfirmationModal';

interface ADRCardProps {
  adr: ADR;
  onAnalyze: (adrId: string) => void;
  onDelete: (adrId: string) => Promise<void>;
  onPushToRAG: (adrId: string) => void;
}

export function ADRCard({ adr, onAnalyze, onDelete, onPushToRAG }: ADRCardProps) {
  const [showModal, setShowModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleAnalyze = async () => {
    setIsAnalyzing(true);
    try {
      await onAnalyze(adr.metadata.id);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await onDelete(adr.metadata.id);
      setShowDeleteModal(false);
    } catch (error) {
      console.error('Failed to delete ADR:', error);
      alert('Failed to delete ADR');
    } finally {
      setIsDeleting(false);
    }
  };

  const handlePushToRAG = () => {
    onPushToRAG(adr.metadata.id);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'accepted':
        return 'bg-green-100 text-green-800';
      case 'proposed':
        return 'bg-yellow-100 text-yellow-800';
      case 'rejected':
        return 'bg-red-100 text-red-800';
      case 'deprecated':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-blue-100 text-blue-800';
    }
  };

  return (
    <>
      <div className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
        <div className="flex justify-between items-start mb-4">
          <h3 className="text-lg font-semibold text-gray-900 line-clamp-2">
            {adr.metadata.title}
          </h3>
          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(adr.metadata.status)}`}>
            {adr.metadata.status}
          </span>
        </div>

        <p className="text-gray-600 text-sm mb-4 line-clamp-3">
          {adr.content.context_and_problem}
        </p>

        <div className="flex flex-wrap gap-1 mb-4">
          {adr.metadata.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded-md"
            >
              {tag}
            </span>
          ))}
          {adr.metadata.tags.length > 3 && (
            <span className="px-2 py-1 bg-gray-50 text-gray-600 text-xs rounded-md">
              +{adr.metadata.tags.length - 3} more
            </span>
          )}
        </div>

        <div className="flex justify-between items-center text-sm text-gray-500 mb-4">
          <span>By {adr.metadata.author}</span>
          <span>{new Date(adr.metadata.created_date).toLocaleDateString()}</span>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => setShowModal(true)}
            className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors"
          >
            View Details
          </button>
          <button
            onClick={handleAnalyze}
            disabled={isAnalyzing}
            className="flex-1 bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isAnalyzing ? 'Analyzing...' : 'Analyze'}
          </button>
        </div>

        <div className="flex gap-2 mt-2">
          <button
            onClick={handlePushToRAG}
            className="flex-1 bg-purple-600 text-white px-4 py-2 rounded-md hover:bg-purple-700 transition-colors text-sm"
          >
            Push to RAG
          </button>
          <button
            onClick={() => setShowDeleteModal(true)}
            className="flex-1 bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700 transition-colors text-sm"
          >
            Delete
          </button>
        </div>
      </div>

      {showModal && (
        <ADRModal
          adr={adr}
          onClose={() => setShowModal(false)}
          onAnalyze={handleAnalyze}
          isAnalyzing={isAnalyzing}
        />
      )}

      {showDeleteModal && (
        <DeleteConfirmationModal
          adrTitle={adr.metadata.title}
          onConfirm={handleDelete}
          onCancel={() => setShowDeleteModal(false)}
          isDeleting={isDeleting}
        />
      )}
    </>
  );
}
