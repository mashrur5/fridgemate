// ApiClient: the web app's only way to talk to the server. Holds the login token.

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const TOKEN_KEY = "fridgemate.token";

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export class ApiClient {
  token: string | null = readToken();
  onUnauthorized: () => void = () => {};

  setToken(token: string | null) {
    this.token = token;
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* private mode: keep it in memory only */
    }
  }

  async request<T = any>(method: string, path: string, body?: unknown, form?: FormData): Promise<T> {
    const headers: Record<string, string> = {};
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    if (body !== undefined) headers["Content-Type"] = "application/json";
    let res: Response;
    try {
      res = await fetch(path, { method, headers, body: form ?? (body !== undefined ? JSON.stringify(body) : undefined) });
    } catch {
      throw new ApiError(0, "Couldn't connect to the server. Is it running?");
    }
    const text = await res.text();
    const data = text ? JSON.parse(text) : null;
    if (!res.ok) {
      let msg = data?.detail ?? res.statusText;
      if (Array.isArray(msg)) msg = msg.map((d: any) => `${d.loc?.slice(1).join(".")}: ${d.msg}`).join("; ");
      if (res.status === 401 && this.token) {
        this.setToken(null);
        this.onUnauthorized();
      }
      throw new ApiError(res.status, String(msg));
    }
    return data as T;
  }

  get = <T = any>(path: string) => this.request<T>("GET", path);
  post = <T = any>(path: string, body?: unknown) => this.request<T>("POST", path, body ?? {});
  patch = <T = any>(path: string, body: unknown) => this.request<T>("PATCH", path, body);
  put = <T = any>(path: string, body: unknown) => this.request<T>("PUT", path, body);
  del = <T = any>(path: string) => this.request<T>("DELETE", path);
  upload = <T = any>(path: string, form: FormData) => this.request<T>("POST", path, undefined, form);
}

export const api = new ApiClient();

export function qs(params: Record<string, string | number | undefined | null>): string {
  const p = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return p.length ? "?" + p.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&") : "";
}
