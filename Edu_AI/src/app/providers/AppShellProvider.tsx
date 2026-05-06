import {
  createContext,
  useContext,
  useMemo,
  type PropsWithChildren,
} from "react";
import type { ThemeName } from "../routing/routes";

export type CourseSummary = {
  id: string;
  module: string;
  title: string;
  uppercaseTitle: string;
  instructor: string;
  progress: number;
  image: string;
  accent: string;
  summary: string;
};

export const defaultCourse: CourseSummary = {
  id: "quantum-advanced",
  module: "Module 4",
  title: "Advanced Quantum Mechanics",
  uppercaseTitle: "ADVANCED QUANTUM MECHANICS",
  instructor: "Dr. Eleanor Stone",
  progress: 65,
  image: "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?auto=format&fit=crop&w=1200&q=80",
  accent: "from-[#0f172a] via-[#1d4ed8] to-[#60a5fa]",
  summary: "Advanced course workspace for wave functions, measurement, and knowledge graph assisted learning.",
};

type AppShellContextValue = {
  selectedCourse: CourseSummary | null;
  setSelectedCourse: (course: CourseSummary | null) => void;
  theme: ThemeName;
  setTheme: (theme: ThemeName) => void;
  logout: () => void;
};

const AppShellContext = createContext<AppShellContextValue | null>(null);

export function AppShellProvider({
  children,
  selectedCourse,
  setSelectedCourse,
  theme,
  setTheme,
  logout,
}: PropsWithChildren<AppShellContextValue>) {
  const value = useMemo(
    () => ({ selectedCourse, setSelectedCourse, theme, setTheme, logout }),
    [selectedCourse, setSelectedCourse, theme, setTheme, logout],
  );

  return <AppShellContext.Provider value={value}>{children}</AppShellContext.Provider>;
}

export function useAppShell() {
  const value = useContext(AppShellContext);

  if (!value) {
    throw new Error("useAppShell must be used inside AppShellProvider.");
  }

  return value;
}
