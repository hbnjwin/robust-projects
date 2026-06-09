import React, { createContext, useContext, useState, useCallback } from "react";

interface AuthState {
  isLoggedIn: boolean;
  user: { id: string; name: string } | null;
}

interface AuthContextValue extends AuthState {
  login: (name: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    isLoggedIn: false,
    user: null,
  });

  const login = useCallback((name: string) => {
    setState({
      isLoggedIn: true,
      user: { id: Date.now().toString(), name },
    });
  }, []);

  const logout = useCallback(() => {
    setState({ isLoggedIn: false, user: null });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
