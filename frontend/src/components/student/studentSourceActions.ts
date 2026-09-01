export type StudentSourceAction = "select" | "preview" | "rename" | "delete" | "retry";

export function getStudentSourceActions(
  library: "course" | "personal",
  status: string,
): StudentSourceAction[] {
  if (library === "course") return ["select", "preview"];
  return status === "failed"
    ? ["select", "preview", "rename", "delete", "retry"]
    : ["select", "preview", "rename", "delete"];
}
