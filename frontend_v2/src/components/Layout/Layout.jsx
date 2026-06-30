import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { Home, Folder, Users, Settings, LogOut } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import './Layout.css';

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path) => {
    return location.pathname === path ? 'active' : '';
  };

  return (
    <div className="layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2 className="logo">Dynostore</h2>
        </div>
        <nav className="sidebar-nav">
          <Link to="/dashboard" className={`nav-link ${isActive('/dashboard')}`}>
            <Home size={20} />
            <span>Dashboard</span>
          </Link>
          <Link to="/groups" className={`nav-link ${isActive('/groups')}`}>
            <Users size={20} />
            <span>Groups</span>
          </Link>
          <Link to="/catalogs" className={`nav-link ${isActive('/catalogs')}`}>
            <Folder size={20} />
            <span>Catalogs</span>
          </Link>
          <div className="nav-divider"></div>
          <Link to="/settings" className={`nav-link ${isActive('/settings')}`}>
            <Settings size={20} />
            <span>Settings</span>
          </Link>
        </nav>
      </aside>

      {/* Main Content Area */}
      <div className="main-content">
        <header className="topbar">
          <div className="search-bar">
            {/* Search placeholder */}
          </div>
          <div className="user-profile">
            <div className="avatar">AD</div>
            <button onClick={handleLogout} className="logout-btn" style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
              <LogOut size={18} />
              <span>Log out</span>
            </button>
          </div>
        </header>
        
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
