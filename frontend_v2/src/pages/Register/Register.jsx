import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserPlus, User, Key, Mail, Building, CheckCircle, AlertTriangle } from 'lucide-react';
import './Register.css';

export default function Register() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [tokenorg, setTokenorg] = useState('');
  const [organizations, setOrganizations] = useState([]);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [toastMessage, setToastMessage] = useState(null);
  
  const navigate = useNavigate();

  useEffect(() => {
    const fetchOrganizations = async () => {
      try {
        const response = await fetch('/api/auth/organization');
        const data = await response.json();
        if (response.ok && data.data && data.data.length > 0) {
          setOrganizations(data.data);
          setTokenorg(data.data[0].tokenorg);
        } else {
          console.error("Failed to fetch organizations:", data);
        }
      } catch (err) {
        console.error("Network error fetching organizations:", err);
      }
    };
    fetchOrganizations();
  }, []);

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    
    // Client-side validations
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (!tokenorg) {
      setError("Please select an organization.");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/auth/user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password, tokenorg })
      });
      const data = await response.json();
      
      if (response.ok && data.codigo === 0) {
        setToastMessage({ type: 'success', text: 'Registration successful! Redirecting to login...' });
        setTimeout(() => {
          navigate('/login', { state: { successMessage: 'Registration successful! Please sign in with your new credentials.' } });
        }, 2000);
      } else {
        setError(data.message || 'Registration failed. Please check your details.');
        setToastMessage({ type: 'error', text: data.message || 'Registration failed.' });
        setTimeout(() => setToastMessage(null), 4000);
      }
    } catch (err) {
      setError('Network error. Please try again.');
      setToastMessage({ type: 'error', text: 'Network error. Please try again.' });
      setTimeout(() => setToastMessage(null), 4000);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="register-container">
      {toastMessage && (
        <div className={`toast-notification ${toastMessage.type}`}>
          {toastMessage.type === 'success' ? <CheckCircle size={20} /> : <AlertTriangle size={20} />}
          <span>{toastMessage.text}</span>
        </div>
      )}

      <div className="register-card card">
        <div className="register-header">
          <h1 className="logo">Dynostore</h1>
          <p className="register-subtitle">Create a new account.</p>
        </div>

        {error && <div className="alert alert-danger" style={{ color: '#ef4444', marginBottom: '1rem', textAlign: 'center', backgroundColor: 'rgba(239, 68, 68, 0.1)', padding: '0.75rem', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.3)' }}>{error}</div>}

        <form onSubmit={handleRegister} className="register-form">
          <div className="form-group">
            <label className="form-label">Username</label>
            <div className="input-with-icon">
              <User size={18} className="input-icon" />
              <input 
                type="text" 
                className="form-control" 
                placeholder="Choose a username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Email</label>
            <div className="input-with-icon">
              <Mail size={18} className="input-icon" />
              <input 
                type="email" 
                className="form-control" 
                placeholder="Enter your email address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
          </div>



          <div className="form-group">
            <label className="form-label">Password</label>
            <div className="input-with-icon">
              <Key size={18} className="input-icon" />
              <input 
                type="password" 
                className="form-control" 
                placeholder="Create a password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Confirm Password</label>
            <div className="input-with-icon">
              <Key size={18} className="input-icon" />
              <input 
                type="password" 
                className="form-control" 
                placeholder="Confirm your password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </div>
          </div>

          <button 
            type="submit" 
            className="btn btn-primary register-submit mt-2"
            disabled={loading}
          >
            {loading ? 'Registering...' : (
              <>
                <UserPlus size={18} />
                Sign Up
              </>
            )}
          </button>
        </form>

        <div className="register-footer">
          <p>Already have an account? <a href="/login">Sign in</a></p>
        </div>
      </div>
    </div>
  );
}
