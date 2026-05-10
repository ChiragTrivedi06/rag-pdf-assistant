import React, { useState } from 'react';
import { uploadDocument } from '../../services/api';

const Sidebar = ({ onFileUploaded }) => {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      await uploadDocument(file);
      onFileUploaded(file.name);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <aside className="sidebar glass-card">
      <div className="sidebar-header">
        <h2>Documents</h2>
      </div>
      
      <div className="upload-section">
        <label className="upload-label">
          <input 
            type="file" 
            accept=".pdf" 
            onChange={handleFileUpload} 
            disabled={uploading}
            hidden 
          />
          <div className="upload-btn btn-primary">
            {uploading ? 'Processing...' : 'Upload PDF'}
          </div>
        </label>
        {error && <p className="error-text">{error}</p>}
      </div>

      <div className="sidebar-footer">
        <p>Production Ready RAG</p>
      </div>
    </aside>
  );
};

export default Sidebar;
