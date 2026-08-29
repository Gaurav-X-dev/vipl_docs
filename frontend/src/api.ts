import axios, { AxiosError } from "axios";

const TOKEN_KEY = "vipl_access_token";
const REFRESH_KEY = "vipl_refresh_token";
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api/v1",
  timeout: 30000,
});
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    if (
      error.response?.status === 401 &&
      !error.config?._retried &&
      localStorage.getItem(REFRESH_KEY)
    ) {
      error.config._retried = true;
      try {
        const { data } = await axios.post(
          `${api.defaults.baseURL}/auth/refresh`,
          { refresh_token: localStorage.getItem(REFRESH_KEY) },
        );
        localStorage.setItem(TOKEN_KEY, data.access_token);
        error.config.headers.Authorization = `Bearer ${data.access_token}`;
        return api(error.config);
      } catch {
        clearSession();
        location.assign("/login");
      }
    }
    return Promise.reject(error);
  },
);
export function saveSession(tokens: {
  access_token: string;
  refresh_token: string;
}) {
  localStorage.setItem(TOKEN_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
}
export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}
export const hasToken = () => Boolean(localStorage.getItem(TOKEN_KEY));
export function errorMessage(error: unknown) {
  const e = error as AxiosError<{
    error?: { message?: string };
    detail?: string;
  }>;
  return (
    e.response?.data?.error?.message ||
    e.response?.data?.detail ||
    e.message ||
    "Something went wrong."
  );
}
/**
 * Fetch a file through the authenticated client and hand it to the browser.
 * Returns a promise so callers can show progress and surface failures.
 */
export async function download(path: string, fallbackName: string) {
  const response = await api.get(path, { responseType: "blob" });
  const disposition = String(response.headers["content-disposition"] || "");
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
  const name = match ? decodeURIComponent(match[1]) : fallbackName;
  const url = URL.createObjectURL(response.data as Blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** Build a querystring from a filter object, dropping empty values. */
export function toParams(input: Record<string, unknown>) {
  const params: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(input)) {
    if (value === undefined || value === null || value === "") continue;
    params[key] = value;
  }
  return params;
}
