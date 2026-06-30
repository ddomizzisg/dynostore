import React, { useState, useEffect } from 'react';
import { Activity, HardDrive, FolderOpen, Zap, CheckCircle, AlertTriangle } from 'lucide-react';
import { getRootCatalogs, getSystemHealth, forceReplication } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import './Dashboard.css';

export default function Dashboard() {
  const { user, userToken } = useAuth();
  const [activeCatalogs, setActiveCatalogs] = useState(0);
  const [healthStatus, setHealthStatus] = useState('Checking...');
  const [loading, setLoading] = useState(true);
  const [isReplicating, setIsReplicating] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);

  useEffect(() => {
    const fetchDashboardData = async () => {
      setLoading(true);
      try {
        // Fetch Active Catalogs
        const catalogs = await getRootCatalogs(userToken);
        setActiveCatalogs(catalogs?.length || 0);

        // Fetch Health Status
        const health = await getSystemHealth();
        setHealthStatus(health?.status === 'ok' ? 'Online' : 'Offline');
      } catch (error) {
        console.error("Error fetching dashboard data:", error);
        setHealthStatus('Offline');
      } finally {
        setLoading(false);
      }
    };
    if (userToken) fetchDashboardData();
  }, [userToken]);

  const handleForceReplication = async () => {
    setIsReplicating(true);
    setToastMessage(null);
    try {
      const response = await forceReplication();
      setToastMessage({ type: 'success', text: response?.message || 'Replication cycle completed successfully.' });
    } catch (error) {
      setToastMessage({ type: 'error', text: 'Replication cycle failed.' });
    } finally {
      setIsReplicating(false);
      // Hide toast after 3 seconds
      setTimeout(() => setToastMessage(null), 3000);
    }
  };

  return (
    <div className="dashboard-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Welcome back, {user?.username || 'User'}</h1>
          <p className="page-subtitle">Overview of your account and system status.</p>
        </div>
      </div>

      {toastMessage && (
        <div className={`toast-notification ${toastMessage.type}`}>
          {toastMessage.type === 'success' ? <CheckCircle size={20} /> : <AlertTriangle size={20} />}
          <span>{toastMessage.text}</span>
        </div>
      )}

      <div className="stats-grid">
        <div className="stat-card glass-card">
          <div className="stat-icon bg-primary-light">
            <FolderOpen size={28} className="text-primary" />
          </div>
          <div className="stat-info">
            <h3>{loading ? '...' : activeCatalogs}</h3>
            <p>Active Catalogs</p>
          </div>
        </div>

        <div className="stat-card glass-card">
          <div className="stat-icon bg-success-light">
            <Activity size={28} className="text-success" />
          </div>
          <div className="stat-info">
            <h3 className={healthStatus === 'Online' ? 'text-success' : 'text-error'}>
              {loading ? '...' : healthStatus}
            </h3>
            <p>System Status</p>
          </div>
        </div>
      </div>

      <div className="dashboard-content mt-4">
        <div className="glass-card quick-actions">
          <h3 className="card-title">Quick Actions</h3>
          <p className="card-description">Trigger manual operations and manage your system.</p>
          <button 
            className="btn btn-action" 
            onClick={handleForceReplication}
            disabled={isReplicating}
          >
            <Zap size={18} />
            {isReplicating ? 'Replicating...' : 'Force Replication'}
          </button>
        </div>
      </div>
    </div>
  );
}
