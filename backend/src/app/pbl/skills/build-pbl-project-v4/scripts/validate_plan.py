#!/usr/bin/env python3
"""Validate PBL planning structure only; never execute generated code or publish."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from pydantic import ValidationError
from app.pbl.project_workflow import ProjectPlan, StepUnit, validate_project_plan, validate_step_unit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path, nargs='?')
    parser.add_argument('--step-unit', type=Path, help='Validate a teaching unit against this plan')
    parser.add_argument('--schema', choices=['plan', 'step'], help='Print the authoritative JSON schema')
    args = parser.parse_args()
    if args.schema:
        print(json.dumps((ProjectPlan if args.schema == 'plan' else StepUnit).model_json_schema(), ensure_ascii=False, indent=2))
        return 0
    if args.plan is None:
        parser.error('plan is required unless --schema is specified')
    try:
        plan = json.loads(args.plan.read_text(encoding='utf-8'))
        if args.step_unit:
            result = validate_step_unit(plan, json.loads(args.step_unit.read_text(encoding='utf-8')))
        else:
            result = validate_project_plan(plan)
    except (OSError, ValueError) as error:
        details = error.errors(include_input=False, include_context=False) if isinstance(error, ValidationError) else str(error)
        print(json.dumps({'structurallyValid': False, 'executionValidated': False, 'publishable': False, 'issues': details}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
