import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, clearSession, hasToken, saveSession } from "./api";
import type { User } from "./types";

type AuthValue = {
  user: User | null;
  loading: boolean;
  login: (
    email: string,
    password: string,
    remember_me?: boolean,
  ) => Promise<void>;
  logout: () => Promise<void>;
  can: (permission: string) => boolean;
};
const AuthContext = createContext<AuthValue | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(hasToken());
  useEffect(() => {
    if (!hasToken()) {
      setLoading(false);
      return;
    }
    api
      .get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => clearSession())
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (!user) return;
    const ping = () =>
      api
        .post("/auth/heartbeat", { page: location.pathname })
        .catch(() => undefined);
    ping();
    const id = setInterval(ping, 60000);
    return () => clearInterval(id);
  }, [user]);
  const value = useMemo<AuthValue>(
    () => ({
      user,
      loading,
      login: async (email, password, remember_me = false) => {
        const { data } = await api.post("/auth/login", {
          email,
          password,
          remember_me,
        });
        saveSession(data.tokens);
        setUser(data.user);
      },
      logout: async () => {
        try {
          await api.post("/auth/logout");
        } finally {
          clearSession();
          setUser(null);
        }
      },
      can: (p) =>
        Boolean(user?.is_super_admin || user?.permissions.includes(p)),
    }),
    [user, loading],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export const useAuth = () => {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider missing");
  return value;
};
