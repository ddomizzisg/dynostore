import { useState, useEffect } from 'react';
import { Plus, Users as UsersIcon } from 'lucide-react';
import { getGroups } from '../../services/api';

export default function Groups() {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchGroups = async () => {
      try {
        const userToken = localStorage.getItem('userToken');
        if (!userToken) throw new Error('Not authenticated');
        const data = await getGroups(userToken);
        setGroups(Array.isArray(data) ? data : (data.data || []));
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchGroups();
  }, []);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Groups</h1>
          <p className="page-subtitle">Manage your organizations and group memberships.</p>
        </div>
        <button className="btn btn-primary">
          <Plus size={18} />
          Create Group
        </button>
      </div>

      <div className="card">
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--color-text-muted)' }}>
                <th style={{ padding: '1rem', fontWeight: 500 }}>Group Name</th>
                <th style={{ padding: '1rem', fontWeight: 500 }}>Members</th>
                <th style={{ padding: '1rem', fontWeight: 500 }}>Your Role</th>
                <th style={{ padding: '1rem', fontWeight: 500 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => (
                <tr key={group.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '1rem' }}>
                    <div className="d-flex align-items-center gap-3">
                      <div className="avatar" style={{ width: '32px', height: '32px', fontSize: '0.8rem' }}>
                        <UsersIcon size={16} />
                      </div>
                      <strong>{group.name}</strong>
                    </div>
                  </td>
                  <td style={{ padding: '1rem', color: 'var(--color-text-muted)' }}>{group.members} users</td>
                  <td style={{ padding: '1rem' }}>
                    <span style={{ 
                      padding: '4px 8px', 
                      borderRadius: '4px', 
                      backgroundColor: group.role === 'Admin' ? 'var(--color-secondary)' : '#f0f0f0',
                      color: group.role === 'Admin' ? 'var(--color-primary)' : 'var(--color-text-muted)',
                      fontSize: '0.85rem',
                      fontWeight: 500
                    }}>
                      {group.role}
                    </span>
                  </td>
                  <td style={{ padding: '1rem' }}>
                    <button className="btn btn-secondary" style={{ padding: '0.4rem 0.8rem' }}>View Details</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
