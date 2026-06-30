import { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [userToken, setUserToken] = useState(localStorage.getItem('userToken'));
  const [accessToken, setAccessToken] = useState(localStorage.getItem('accessToken'));

  const login = (uToken, aToken) => {
    localStorage.setItem('userToken', uToken);
    localStorage.setItem('accessToken', aToken);
    setUserToken(uToken);
    setAccessToken(aToken);
  };

  const logout = () => {
    localStorage.removeItem('userToken');
    localStorage.removeItem('accessToken');
    setUserToken(null);
    setAccessToken(null);
  };

  // Intercept fetch API failures (specifically 401 Unauthorized) globally if possible
  // We will expose a method or just handle it at the component level
  
  return (
    <AuthContext.Provider value={{ userToken, accessToken, login, logout, isAuthenticated: !!userToken && userToken !== 'undefined' }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
