import { create } from 'zustand';

interface UiStore {
  isCourseSiderCollapsed: boolean;
  setCourseSiderCollapsed: (collapsed: boolean) => void;
  toggleCourseSider: () => void;
  setFocusMode: (isFocus: boolean) => void;
}

export const useUiStore = create<UiStore>((set, get) => ({
  isCourseSiderCollapsed: false,
  setCourseSiderCollapsed: (collapsed) => set({ isCourseSiderCollapsed: collapsed }),
  toggleCourseSider: () => set({ isCourseSiderCollapsed: !get().isCourseSiderCollapsed }),
  setFocusMode: (isFocus) => set({ isCourseSiderCollapsed: isFocus }),
}));

