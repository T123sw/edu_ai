import { create } from 'zustand';
import {
  fetchCourses,
  createCourseBackend,
  updateCourseDetail,
  deleteCourseBackend,
  type BackendCourse,
} from '../../services/teacher/api';

export interface Course {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  createdAt?: string;
  objectives?: string[]; // 教学目标
  knowledgeGraph?: string; // 课程知识图谱（可以是JSON字符串或URL）
  masterKnowledgeBase?: KnowledgeBaseItem[];
  difficulty?: string;
  duration?: string;
}

export interface KnowledgeBaseItem {
  id: string;
  name: string;
  type: 'file' | 'folder' | 'web';
  url?: string;
  fileType?: string;
  size?: number;
  uploadedAt?: string;
  children?: KnowledgeBaseItem[];
}

interface CourseState {
  courses: Course[];
  currentCourse: Course | null;
  loading: boolean;
  loadCoursesFromBackend: () => Promise<void>;
  setCurrentCourse: (courseId: string) => void;
  addCourse: (course: Omit<Course, 'createdAt'>) => Promise<void>;
  updateCourse: (id: string, course: Partial<Course>) => Promise<void>;
  deleteCourse: (id: string) => Promise<void>;
  addKnowledgeBaseItem: (courseId: string, item: KnowledgeBaseItem, parentId?: string) => void;
  removeKnowledgeBaseItem: (courseId: string, itemId: string) => void;
}

export const useCourseStore = create<CourseState>((set, get) => ({
  courses: [],
  currentCourse: null,
  loading: false,

  loadCoursesFromBackend: async () => {
    set({ loading: true });
    try {
      const list = await fetchCourses();
      const current = get().courses;
      const courses: Course[] = list.map((c: BackendCourse) => ({
        ...c,
        masterKnowledgeBase: current.find(cc => cc.id === c.id)?.masterKnowledgeBase || [],
      }));
      set({ courses, loading: false });
    } catch (e) {
      console.error(e);
      set({ loading: false });
    }
  },

  setCurrentCourse: (courseId) => {
    const course = get().courses.find(c => c.id === courseId);
    set({ currentCourse: course || null });
  },

  addCourse: async (course) => {
    const payload: BackendCourse = {
      id: course.id || `course-${Date.now()}`,
      title: course.title,
      description: course.description,
      icon: course.icon,
      color: course.color,
      objectives: course.objectives,
      knowledgeGraph: course.knowledgeGraph,
    };
    const saved = await createCourseBackend(payload);
    set((state) => ({
      courses: [...state.courses, { ...saved, masterKnowledgeBase: [] }],
    }));
  },

  updateCourse: async (id, updates) => {
    const state = get();
    const existing = state.courses.find(course => course.id === id);
    if (!existing) return;

    const payload: BackendCourse = {
      id,
      title: updates.title ?? existing.title,
      description: updates.description ?? existing.description,
      icon: existing.icon,
      color: existing.color,
      objectives: updates.objectives ?? existing.objectives,
      knowledgeGraph: updates.knowledgeGraph ?? existing.knowledgeGraph,
    };

    const saved = await updateCourseDetail(payload);
    set({
      courses: state.courses.map(course =>
        course.id === id ? { ...course, ...saved } : course
      ),
    });
  },

  deleteCourse: async (id) => {
    await deleteCourseBackend(id);
    set((state) => ({
      courses: state.courses.filter(course => course.id !== id),
    }));
  },

  addKnowledgeBaseItem: (courseId, item, parentId) => set((state) => ({
    courses: state.courses.map(course => {
      if (course.id !== courseId) return course;
      const kb = course.masterKnowledgeBase || [];
      if (parentId) {
        const addToFolder = (items: KnowledgeBaseItem[]): KnowledgeBaseItem[] => {
          return items.map(it => {
            if (it.id === parentId) {
              return {
                ...it,
                children: [...(it.children || []), item],
              };
            }
            if (it.children) {
              return {
                ...it,
                children: addToFolder(it.children),
              };
            }
            return it;
          });
        };
        return {
          ...course,
          masterKnowledgeBase: addToFolder(kb),
        };
      } else {
        return {
          ...course,
          masterKnowledgeBase: [...kb, item],
        };
      }
    }),
  })),

  removeKnowledgeBaseItem: (courseId, itemId) => set((state) => ({
    courses: state.courses.map(course => {
      if (course.id !== courseId) return course;
      const kb = course.masterKnowledgeBase || [];
      const removeItem = (items: KnowledgeBaseItem[]): KnowledgeBaseItem[] => {
        return items.filter(it => {
          if (it.id === itemId) return false;
          if (it.children) {
            it.children = removeItem(it.children);
          }
          return true;
        });
      };
      return {
        ...course,
        masterKnowledgeBase: removeItem(kb),
      };
    }),
  })),
}));