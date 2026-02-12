/**
 * Supabase Client - Mobile SDK Integration
 *
 * Initializes the Supabase client with a custom storage adapter
 * backed by Expo SecureStore for encrypted token persistence.
 *
 * When SUPABASE_URL and SUPABASE_ANON_KEY are not set the client
 * is not created — callers must check `config.USE_SUPABASE_AUTH`
 * before accessing `supabase`.
 */

import 'react-native-url-polyfill/auto';
import { createClient, SupabaseClient } from '@supabase/supabase-js';
import * as SecureStore from 'expo-secure-store';
import { config } from '../constants/config';

// ---------------------------------------------------------------------------
// Custom storage adapter for Supabase Auth (encrypted via SecureStore)
// ---------------------------------------------------------------------------

const supabaseStorage = {
  getItem: async (key: string): Promise<string | null> => {
    try {
      return await SecureStore.getItemAsync(key);
    } catch {
      return null;
    }
  },
  setItem: async (key: string, value: string): Promise<void> => {
    try {
      await SecureStore.setItemAsync(key, value);
    } catch {
      // Silently ignore — storage failure shouldn't crash the app
    }
  },
  removeItem: async (key: string): Promise<void> => {
    try {
      await SecureStore.deleteItemAsync(key);
    } catch {
      // Silently ignore
    }
  },
};

// ---------------------------------------------------------------------------
// Client singleton
// ---------------------------------------------------------------------------

let _supabase: SupabaseClient | null = null;

/**
 * Returns the shared Supabase client instance.
 * Creates it on first call.  Returns `null` when Supabase is not configured.
 */
export function getSupabaseClient(): SupabaseClient | null {
  if (!config.USE_SUPABASE_AUTH) {
    return null;
  }

  if (!_supabase) {
    _supabase = createClient(config.SUPABASE_URL, config.SUPABASE_ANON_KEY, {
      auth: {
        storage: supabaseStorage,
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: false,
      },
    });
  }

  return _supabase;
}

/**
 * Convenience re-export — will be `null` when Supabase is not configured.
 * Prefer `getSupabaseClient()` for lazy initialization.
 */
export const supabase = config.USE_SUPABASE_AUTH
  ? getSupabaseClient()
  : null;
