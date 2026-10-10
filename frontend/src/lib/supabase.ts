import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { config } from "./config";

let client: SupabaseClient | null | undefined;

/** Browser Supabase client, used only for sign-in. Null when not configured. */
export function getSupabase(): SupabaseClient | null {
  if (client !== undefined) return client;
  client =
    typeof window !== "undefined" && config.supabaseUrl && config.supabaseAnonKey
      ? createClient(config.supabaseUrl, config.supabaseAnonKey, {
          auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
        })
      : null;
  return client;
}
