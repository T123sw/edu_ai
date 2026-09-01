export type AssessmentPublishDraft = {
  status: string
  items: Array<{ assessment_item_id: string }>
  quality: {
    publishable: boolean
    issues: Array<{ message: string }>
  }
}

export function getAssessmentPublishBlockers(
  draft: AssessmentPublishDraft | null | undefined,
): string[] {
  if (!draft || draft.items.length === 0) return ['请先配置正式测评']
  if (draft.quality.publishable) return []
  return draft.quality.issues.length > 0
    ? draft.quality.issues.map((issue) => issue.message)
    : ['测评尚未通过发布校验']
}
