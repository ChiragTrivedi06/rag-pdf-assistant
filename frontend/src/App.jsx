import React, { useState } from 'react';
import './styles/theme.css';
import './App.css';
import ChatWindow from './components/chat/ChatWindow';
import Sidebar from './components/layout/Sidebar';

function App() {
  const [currentFile, setCurrentFile] = useState(null);

  return (
    <div className="app-container">
      <Sidebar onFileUploaded={(file) => setCurrentFile(file)} />
      <main className="main-content">
        <header className="app-header">
          <h1>RAG Production AI</h1>
          {currentFile && (
            <div className="current-doc">
              <span className="dot"></span>
              Active Document: {currentFile}
            </div>
          )}
        </header>
        <ChatWindow />
      </main>
    </div>
  );
}

export default App;
