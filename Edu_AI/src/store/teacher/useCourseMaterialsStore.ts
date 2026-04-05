import { create } from 'zustand';
import type { GeneratedFile } from './useStore';

export interface CourseMaterial extends GeneratedFile {
  addedAt: string;
  courseId?: string;
}

interface CourseMaterialsState {
  materials: CourseMaterial[];
  addMaterial: (material: CourseMaterial) => void;
  removeMaterial: (id: string) => void;
  getMaterialsByType: (type: GeneratedFile['type']) => CourseMaterial[];
  setMaterials: (materials: CourseMaterial[]) => void;
}

export const useCourseMaterialsStore = create<CourseMaterialsState>((set, get) => ({
  materials: [],
  
  addMaterial: (material) => set((state) => ({
    materials: [...state.materials, material],
  })),
  
  removeMaterial: (id) => set((state) => ({
    materials: state.materials.filter(m => m.id !== id),
  })),
  
  getMaterialsByType: (type) => {
    return get().materials.filter(m => m.type === type);
  },
  
  setMaterials: (materials) => set({ materials }),
}));

