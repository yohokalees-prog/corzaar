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

export type Course = { id: string; title: string; category: string; duration: string; fees: number; rating: number; students: number; mode: string; description: string; image_key: string; institute_id: string; status?: string; curriculum?: string[]; reviews_count?: number };
export type Institute = { id: string; name: string; city: string; rating: number; accreditation: string; students: string; description: string; image_key: string; status: string };
export type User = { id: string; role: "student" | "merchant" | "admin"; full_name?: string; mobile?: string; email?: string; profile_complete?: boolean; referral_code?: string; wallet_balance?: number };
export type Review = { id: string; rating: number; text: string; name: string; created_at: string };
export type Session = { id: string; date: string; topic?: string };
export type Batch = { id: string; course_id: string; course_title?: string; schedule: string; capacity: number; enrolled: number; coordinator: string; start_date: string; end_date: string; meet_link?: string; status: string; sessions?: Session[] };
export type Coupon = { id: string; code: string; description?: string; discount_percent: number; course_id?: string | null; merchant_id?: string; status: string; title?: string; subtitle?: string };
export type Enrollment = { id: string; course_id: string; status: string; payment_status?: string; amount?: number; discount?: number; wallet_used?: number; coupon_code?: string | null; referral_code?: string | null; receipt?: string; progress?: number; completed_items?: string[]; certificate_id?: string; completed_at?: string; course?: Course };
export type Refund = { id: string; enrollment_id: string; course_title?: string; amount?: number; reason: string; status: string; student_name?: string; created_at: string };
export type AuditLog = { id: string; action: string; module: string; role: string; actor_name?: string; detail?: string; created_at: string };
export type Referral = { code: string; reward_per_referral: number; discount_percent: number; wallet_balance: number; count: number; friends: { amount: number; created_at: string; friend_name: string }[] };
export type PayoutHistory = { id: string; merchant_id: string; amount: number; method: string; reference?: string; notes?: string; status: string; created_at: string };
export type PayoutLedger = { merchant_id: string; merchant_name: string; institute?: any; gross: number; paid_out: number; pending: number };
export type Cashout = { id: string; student_id?: string; student_name?: string; amount: number; upi_id: string; status: string; reference?: string; created_at: string };
export type Insights = { rating_trend: { week: string; average: number; count: number }[]; top_courses: { id: string; title: string; rating: number; reviews_count: number; students: number }[]; curriculum_dropoff: { id: string; title: string; enrolled: number; items: { item: string; completed: number; pct: number }[] }[] };
export type ShareLinks = { certificate_url: string; pdf_url: string; linkedin: string; twitter: string; whatsapp: string; title: string };
