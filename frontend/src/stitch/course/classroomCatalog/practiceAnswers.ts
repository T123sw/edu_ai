export function isMultipleChoice(type?: string): boolean {
  return ["multiple_choice", "multi_choice", "multiple", "multi-select", "多选题"].includes(type || "");
}

// Standard practice questions use letter keys even when the display text has no prefix.
export function practiceOptionValue(option: string, index: number): string {
  return option.match(/^\s*([A-Z])(?:[.、:：)）\s])/i)?.[1].toUpperCase() || String.fromCharCode(65 + index);
}
