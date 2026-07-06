import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { LogIn, Key, Mail, CheckCircle, AlertTriangle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import './Login.css';

export default function Login() {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [toastMessage, setToastMessage] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  useEffect(() => {
    if (location.state?.successMessage) {
      setSuccess(location.state.successMessage);
      setToastMessage({ type: 'success', text: location.state.successMessage });
      setTimeout(() => setToastMessage(null), 5000);
      // Clear state so refresh doesn't show it again
      window.history.replaceState({}, document.title);
    }
  }, [location]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');
    
    try {
      const response = await fetch('/api/auth/user/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: identifier, password: password })
      });
      const data = await response.json();
      
      if (response.ok && data.data) {
        login(data.data.tokenuser, data.data.access_token);
        navigate('/dashboard');
      } else {
        const errorMsg = data.message || 'Login failed. Please check your credentials.';
        setError(errorMsg);
        setToastMessage({ type: 'error', text: errorMsg });
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
    <div className="login-container">
      {toastMessage && (
        <div className={`toast-notification ${toastMessage.type}`} style={{ position: 'fixed', top: '1.5rem', right: '1.5rem', background: 'rgba(17, 24, 39, 0.9)', backdropFilter: 'blur(12px)', border: '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '8px', padding: '1rem 1.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'white', zIndex: 1000, animation: 'slideIn 0.3s ease forwards', boxShadow: '0 10px 25px rgba(0, 0, 0, 0.3)', borderLeft: toastMessage.type === 'success' ? '4px solid #10b981' : '4px solid #ef4444' }}>
          {toastMessage.type === 'success' ? <CheckCircle size={20} color="#10b981" /> : <AlertTriangle size={20} color="#ef4444" />}
          <span>{toastMessage.text}</span>
        </div>
      )}

      <div className="login-card card">
        <div className="login-header">
          <h1 className="logo">Dynostore</h1>
          <p className="login-subtitle">Welcome back. Please enter your details.</p>
        </div>

        {error && <div className="alert alert-danger" style={{ color: '#ef4444', marginBottom: '1rem', textAlign: 'center', backgroundColor: 'rgba(239, 68, 68, 0.1)', padding: '0.75rem', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.3)' }}>{error}</div>}
        {success && <div className="alert alert-success" style={{ color: '#10b981', marginBottom: '1rem', textAlign: 'center', backgroundColor: 'rgba(16, 185, 129, 0.1)', padding: '0.75rem', borderRadius: '8px', border: '1px solid rgba(16, 185, 129, 0.3)' }}>{success}</div>}

        <form onSubmit={handleLogin} className="login-form">
          <div className="form-group">
            <label className="form-label">Email or Username</label>
            <div className="input-with-icon">
              <Mail size={18} className="input-icon" />
              <input 
                type="text" 
                className="form-control" 
                placeholder="Enter your email or username"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
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
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="login-actions">
            <label className="checkbox-container">
              <input type="checkbox" />
              <span>Remember me</span>
            </label>
            <a href="#" className="forgot-password">Forgot password?</a>
          </div>

          <button 
            type="submit" 
            className="btn btn-primary login-submit"
            disabled={loading}
          >
            {loading ? 'Signing in...' : (
              <>
                <LogIn size={18} />
                Sign In
              </>
            )}
          </button>
        </form>

        <div className="login-footer">
          <p>Don't have an account? <a href="/register">Sign up</a></p>
        </div>
      </div>
    </div>
  );
}
