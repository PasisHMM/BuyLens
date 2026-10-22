"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { Toaster, type ToastApi, useToastState } from "@/components/ui/Toast";
import { type ApiClient, createApiClient, type Profile } from "@/lib/api";

type AppState = {
  api: ApiClient;
  profile: Profile | null;
  profileLoaded: boolean;
  reloadProfile: () => Promise<void>;
  toast: ToastApi;
};

const AppContext = createContext<AppState | null>(null);

export function Providers({ children }: { children: React.ReactNode }) {
  const api = useMemo(() => createApiClient(), []);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profileLoaded, setProfileLoaded] = useState(false);
  const toastState = useToastState();

  const reloadProfile = useCallback(async () => {
    try {
      setProfile(await api.getProfile());
    } finally {
      setProfileLoaded(true);
    }
  }, [api]);

  useEffect(() => {
    void reloadProfile();
  }, [reloadProfile]);

  const value = useMemo(
    () => ({
      api,
      profile,
      profileLoaded,
      reloadProfile,
      toast: toastState.api,
    }),
    [api, profile, profileLoaded, reloadProfile, toastState.api],
  );

  return (
    <AppContext.Provider value={value}>
      {children}
      <Toaster state={toastState} />
    </AppContext.Provider>
  );
}

export function useApp(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside <Providers>");
  return ctx;
}
