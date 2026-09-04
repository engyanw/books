import axios from "axios";

export const api = axios.create({ baseURL: "/api", timeout: 15000 });

// 请求拦截：附加 Bearer token
api.interceptors.request.use((config) => {
  const tok = localStorage.getItem("klces_token");
  if (tok) config.headers.Authorization = `Bearer ${tok}`;
  return config;
});

// 响应拦截：401 自动登出并跳登录
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("klces_token");
      localStorage.removeItem("klces_user");
      if (location.pathname !== "/login" && location.pathname !== "/register") {
        location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

// 通用请求封装：GET
export async function get<T>(url: string, params?: Record<string, any>): Promise<T> {
  const { data } = await api.get(url, { params });
  return data;
}
export async function post<T>(url: string, body?: Record<string, any>): Promise<T> {
  const { data } = await api.post(url, body);
  return data;
}
export async function patch<T>(url: string, body?: Record<string, any>): Promise<T> {
  const { data } = await api.patch(url, body);
  return data;
}
export async function put<T>(url: string, body?: Record<string, any>): Promise<T> {
  const { data } = await api.put(url, body);
  return data;
}
export async function del<T>(url: string): Promise<T> {
  const { data } = await api.delete(url);
  return data;
}
