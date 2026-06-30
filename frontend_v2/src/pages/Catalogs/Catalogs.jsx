import { useState, useEffect } from 'react';
import { Plus, MoreVertical, FileText, Folder as FolderIcon, ChevronRight } from 'lucide-react';
import { getRootCatalogs, getCatalogContents } from '../../services/api';

export default function Catalogs() {
  const [currentPath, setCurrentPath] = useState([{ name: 'Root', token: null }]);
  const [catalogs, setCatalogs] = useState([]);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchContents = async () => {
      setLoading(true);
      setError(null);
      try {
        const userToken = localStorage.getItem('userToken');
        if (!userToken) throw new Error('Not authenticated');

        const currentFolder = currentPath[currentPath.length - 1];

        if (currentFolder.token === null) {
          // Fetch root catalogs
          const rootCats = await getRootCatalogs(userToken);
          setCatalogs(rootCats);
          setFiles([]);
        } else {
          // Fetch subcatalogs and files
          const contents = await getCatalogContents(userToken, currentFolder.token);
          setCatalogs(contents.catalogs);
          setFiles(contents.files);
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchContents();
  }, [currentPath]);

  const navigateToFolder = (catalog) => {
    setCurrentPath([...currentPath, { name: catalog.namecatalog, token: catalog.tokencatalog }]);
  };

  const navigateToBreadcrumb = (index) => {
    setCurrentPath(currentPath.slice(0, index + 1));
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Catalogs</h1>
          <p className="page-subtitle">Manage your files and catalogs.</p>
        </div>
        <button className="btn btn-primary">
          <Plus size={18} />
          Create Catalog
        </button>
      </div>

      <div className="card mb-4" style={{ padding: '1rem 1.5rem' }}>
        <div className="d-flex align-items-center" style={{ gap: '0.5rem', fontWeight: 500 }}>
          {currentPath.map((crumb, index) => (
            <div key={crumb.token || 'root'} className="d-flex align-items-center" style={{ gap: '0.5rem' }}>
              <button 
                onClick={() => navigateToBreadcrumb(index)}
                style={{ 
                  background: 'none', border: 'none', cursor: 'pointer', 
                  color: index === currentPath.length - 1 ? 'var(--color-text-main)' : 'var(--color-primary)',
                  fontWeight: index === currentPath.length - 1 ? 600 : 500,
                  fontSize: '1rem'
                }}
              >
                {crumb.name}
              </button>
              {index < currentPath.length - 1 && <ChevronRight size={16} color="var(--color-text-muted)" />}
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ flex: '1' }}>
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h3 className="card-title mb-0">Contents</h3>
        </div>
        
        {loading ? (
          <p style={{ padding: '1rem', color: 'var(--color-text-muted)' }}>Loading...</p>
        ) : error ? (
          <p style={{ padding: '1rem', color: 'var(--color-danger)' }}>{error}</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--color-text-muted)' }}>
                  <th style={{ padding: '1rem', fontWeight: 500 }}>Name</th>
                  <th style={{ padding: '1rem', fontWeight: 500 }}>Description</th>
                  <th style={{ padding: '1rem', fontWeight: 500 }}>Type</th>
                  <th style={{ padding: '1rem', fontWeight: 500 }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {catalogs.length === 0 && files.length === 0 && (
                  <tr>
                    <td colSpan="4" style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-muted)' }}>
                      This folder is empty.
                    </td>
                  </tr>
                )}
                
                {/* Render Folders */}
                {catalogs.map((catalog) => (
                  <tr 
                    key={catalog.tokencatalog} 
                    style={{ borderBottom: '1px solid var(--border-color)', cursor: 'pointer' }}
                    onClick={() => navigateToFolder(catalog)}
                    className="hover-row"
                  >
                    <td style={{ padding: '1rem' }}>
                      <div className="d-flex align-items-center gap-3">
                        <FolderIcon size={18} color="var(--color-primary)" fill="var(--color-secondary)" />
                        <strong>{catalog.namecatalog}</strong>
                      </div>
                    </td>
                    <td style={{ padding: '1rem', color: 'var(--color-text-muted)' }}>{catalog.description || 'Folder'}</td>
                    <td style={{ padding: '1rem', color: 'var(--color-text-muted)' }}>Catalog</td>
                    <td style={{ padding: '1rem' }}>
                      <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }} onClick={(e) => e.stopPropagation()}>
                        <MoreVertical size={18} />
                      </button>
                    </td>
                  </tr>
                ))}

                {/* Render Files */}
                {files.map((file) => (
                  <tr key={file.tokenfile} style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <td style={{ padding: '1rem' }}>
                      <div className="d-flex align-items-center gap-3">
                        <FileText size={18} color="var(--color-text-muted)" />
                        {file.namefile}
                      </div>
                    </td>
                    <td style={{ padding: '1rem', color: 'var(--color-text-muted)' }}>{file.description || 'File'}</td>
                    <td style={{ padding: '1rem', color: 'var(--color-text-muted)' }}>{file.typefile || 'File'}</td>
                    <td style={{ padding: '1rem' }}>
                      <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)' }}>
                        <MoreVertical size={18} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      
      {/* Adding some inline styles for the hover effect on rows */}
      <style>{`
        .hover-row:hover {
          background-color: var(--color-background);
        }
      `}</style>
    </div>
  );
}
