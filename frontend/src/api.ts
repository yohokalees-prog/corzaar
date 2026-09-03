import Constants from "expo-constants";

const configuredUrl = Constants.expoConfig?.extra?.backendUrl || process.env.EXPO_BACKEND_URL || process.env.EXPO_PUBLIC_BACKEND_URL || "";
const API_URL = configuredUrl.replace(/\/$/, "") + "/api";

export async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.message || "Something went wrong");
  return data as T;
}

export const get = <T,>(path: string, token?: string) => request<T>(path, {}, token);
export const post = <T,>(path: string, body: unknown, token?: string) => request<T>(path, { method: "POST", body: JSON.stringify(body) }, token);
export const put = <T,>(path: string, body: unknown, token?: string) => request<T>(path, { method: "PUT", body: JSON.stringify(body) }, token);
export const remove = <T,>(path: string, token?: string) => request<T>(path, { method: "DELETE" }, token);

export type Course = { id: string; title: string; category: string; duration: string; fees: number; rating: number; students: number; mode: string; description: string; image_key: string; institute_id: string };
export type Institute = { id: string; name: string; city: string; rating: number; accreditation: string; students: string; description: string; image_key: string; status: string };
export type User = { id: string; role: "student" | "merchant" | "admin"; full_name?: string; mobile?: string; email?: string; profile_complete?: boolean };