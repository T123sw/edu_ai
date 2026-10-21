from __future__ import annotations
from typing import Literal
from uuid import UUID
import math
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TEMPLATE_VERSION = 'js-function-v1'
ALGORITHM_PATH = '/src/algorithm.js'

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Contract(StrictModel):
    exportName: Literal['quickSort']
    parameterName: Literal['array']
    inputType: Literal['finite_number_array']
    outputType: Literal['ascending_number_array']
    mutatesInput: Literal[False]
    returnsNewArray: Literal[True]

class NumericArrays(StrictModel):
    @field_validator('input', 'expected', check_fields=False, mode='before')
    @classmethod
    def finite_numbers(cls, value):
        if not isinstance(value, list) or len(value) > 1000 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1.7976931348623157e308 for v in value):
            raise ValueError('必须是至多 1000 个有限数字组成的数组')
        return value

class NumberCase(NumericArrays):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    input: list[int | float]
    expected: list[int | float]

class Example(NumericArrays):
    input: list[int | float]
    expected: list[int | float]
    explanation: str

class Hint(StrictModel):
    id: str
    title: str
    body: str

class ExerciseTask(StrictModel):
    id: Literal['implement-sort']
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    instructionsMarkdown: str = Field(min_length=1)
    explanationMarkdown: str = Field(min_length=1)
    hints: list[Hint]
    examples: list[Example] = Field(min_length=1)

class GeneratedExerciseCandidate(StrictModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    contract: Contract
    tasks: list[ExerciseTask] = Field(min_length=1, max_length=1)
    starterCode: str = Field(min_length=1)
    testCases: list[NumberCase]
    referenceSolution: str = Field(min_length=1)

    @field_validator('starterCode','referenceSolution')
    @classmethod
    def source_bound(cls,value):
        if len(value.encode('utf-8'))>131072: raise ValueError('源码超过运行环境限制')
        return value

class PublishedTask(ExerciseTask):
    testCaseIds: list[str]

class ExerciseArtifact(StrictModel):
    schemaVersion: Literal[1] = 1
    exerciseId: str
    artifactVersion: int = Field(ge=1)
    templateVersion: Literal['js-function-v1'] = TEMPLATE_VERSION
    runtimeKind: Literal['js_function'] = 'js_function'
    topic: str
    title: str
    summary: str
    contract: Contract
    tasks: list[PublishedTask]
    starterCode: str
    testCases: list[NumberCase]
    validationSummary: dict

class CreateExercise(StrictModel):
    topic: str = Field(min_length=1,max_length=4000)
    request_id: UUID
    @field_validator('topic')
    @classmethod
    def trimmed(cls, value):
        if not value.strip(): raise ValueError('请输入练习主题')
        return value.strip()

class WorkspacePatch(StrictModel):
    artifactVersion: int = Field(ge=1)
    expectedRevision: int = Field(ge=0)
    mutationId: UUID
    files: dict[str,str]
    activeTaskId: str = Field(min_length=1,max_length=200)
    customInputText: str
    @field_validator('files')
    @classmethod
    def editable_only(cls,value):
        if not value or len(value)>32 or sum(len(k.encode('utf-8'))+len(v.encode('utf-8')) for k,v in value.items())>524288: raise ValueError('源码超过运行环境限制')
        return value
    @field_validator('customInputText')
    @classmethod
    def input_bound(cls,value):
        if len(value.encode('utf-8'))>131072: raise ValueError('输入超过运行环境限制')
        return value

class Workspace(StrictModel):
    exerciseId: str
    artifactVersion: int
    revision: int
    files: dict[str,str]
    activeTaskId: str
    customInputText: str
    updatedAt: float

class RuntimeErrorInfo(StrictModel):
    code: str
    message: str = Field(max_length=2000)

class CaseResult(NumericArrays):
    caseId: str
    status: Literal['passed','failed','error','timeout','canceled']
    actual: list[int|float] | None = None
    expected: list[int|float]
    inputAfter: list[int|float] | None = None
    returnedSameReference: bool | None = None
    error: RuntimeErrorInfo | None = None

class RunRecord(StrictModel):
    runId: UUID
    exerciseId: str
    artifactVersion: int = Field(ge=1)
    templateVersion: Literal['js-function-v1']
    taskId: Literal['implement-sort']
    codeHash: str = Field(pattern=r'^[a-f0-9]{64}$')
    code: str
    mode: Literal['sample','check']
    cases: list[NumberCase]
    status: Literal['passed','failed','error','timeout','canceled']
    results: list[CaseResult]
    durationMs: float = Field(ge=0, allow_inf_nan=False)
    evidenceSource: Literal['browser_reported'] = 'browser_reported'
    @model_validator(mode='after')
    def bounded(self):
        if len(self.code.encode('utf-8'))>131072: raise ValueError('源码超过运行环境限制')
        for result in self.results:
            for values in (result.actual,result.inputAfter):
                if values is not None and (len(values)>1000 or any(not math.isfinite(v) for v in values)):
                    raise ValueError('结果无效或过大')
        return self
