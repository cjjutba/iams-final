import { create } from 'zustand'

interface BreadcrumbStore {
  /** Override label for the last breadcrumb segment (e.g. user name, schedule name) */
  label: string | null
  setLabel: (label: string | null) => void
}

export const useBreadcrumbStore = create<BreadcrumbStore>((set) => ({
  label: null,
  setLabel: (label) => set({ label }),
}))
