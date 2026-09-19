"""Validate explicit coverage without pretending ID checks prove semantic truth."""

def validate_coverage(rows, brief, findings):
    ids = [row.requirement_id for row in rows]
    expected = {r.requirement_id for r in brief.requirements}
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValueError('coverage 必须逐项且不重复覆盖全部需求 ID：' + ', '.join(sorted(expected)))
    known = {f.finding_id for f in findings}
    for row in rows:
        if len(row.finding_ids) != len(set(row.finding_ids)) or not set(row.finding_ids) <= known:
            raise ValueError(f'{row.requirement_id}: coverage 引用了不存在或重复的 finding_id')


def validate_ready(summary, brief):
    validate_coverage(summary.coverage, brief, summary.findings)
    gaps = [r.requirement_id for r in summary.coverage if r.status != 'covered']
    if gaps:
        raise ValueError('需求依据仍不充分，请补资料或 report_research_blocker：' + ', '.join(gaps))
