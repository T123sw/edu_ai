import { create } from 'zustand';
import type { GeneratedFile } from './useStore';
import {
  pinCourseMaterialInList,
  sortCourseMaterials,
  upsertCourseMaterialInList,
} from '../../services/teacher/materials.helpers';

export interface CourseMaterial extends GeneratedFile {
  addedAt: string;
  courseId?: string;
  isPinned?: boolean;
  pinnedAt?: string;
}

interface CourseMaterialsState {
  materials: CourseMaterial[];
  addMaterial: (material: CourseMaterial) => void;
  removeMaterial: (id: string) => void;
  pinMaterial: (id: string, isPinned: boolean, pinnedAt?: string) => void;
  getMaterialsByType: (type: GeneratedFile['type']) => CourseMaterial[];
  setMaterials: (materials: CourseMaterial[]) => void;
}

export const useCourseMaterialsStore = create<CourseMaterialsState>((set, get) => ({
  materials: [],
  
  addMaterial: (material) => set((state) => ({
    materials: upsertCourseMaterialInList(state.materials, material),
  })),
  
  removeMaterial: (id) => set((state) => ({
    materials: state.materials.filter(m => m.id !== id),
  })),

  pinMaterial: (id, isPinned, pinnedAt) => set((state) => ({
    materials: pinCourseMaterialInList(state.materials, id, isPinned, pinnedAt),
  })),
  
  getMaterialsByType: (type) => {
    return sortCourseMaterials(get().materials.filter(m => m.type === type));
  },
  
  setMaterials: (materials) => set({ materials: sortCourseMaterials(materials) }),
}));

