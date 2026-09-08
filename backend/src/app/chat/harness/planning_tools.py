"""Model-owned planning. Tools validate data and persist decisions, not language."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class WorkspaceSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scope_type: Literal['course', 'knowledge_point']
    scope_id: str | None = None
    topic: str = Field(min_length=1, max_length=300)


class WorkingMemory(BaseModel):
    model_config = ConfigDict(extra='forbid')
    goal: str = Field(default='', max_length=1000)
    confirmed_facts: list[str] = Field(default_factory=list, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=10)
    plan: list[str] = Field(default_factory=list, max_length=12)
    next_action: str = Field(default='', max_length=1000)
    blocker: str = Field(default='', max_length=1000)


PLANNING_TOOLS = {
    'select_workspace': (WorkspaceSelection, '根据用户主题与课程目录选择资料归属。知识点 ID 必须来自目录；可选择课程级。topic 保留用户具体主题，不要求逐字匹配目录。不删除或取消其他任务。'),
    'update_working_memory': (WorkingMemory, '保存当前目标、用户已确认事实、单独列出的假设、计划、下一步和阻塞原因。替换上次规划；由模型理解当前意图，不改变真实任务或权限。'),
}


class PlanningToolsMixin:
    def planning_context(self):
        from app.chat.application.knowledge_context import knowledge_candidates
        catalog = knowledge_candidates(self.course_storage.get_knowledge_graph(self.request.course_id)) if self.course_storage and self.request.course_id else []
        states = []
        for item in self.session.data['outlines'].values():
            state = {k: item.get(k) for k in ('outline_id', 'revision', 'subject', 'workspace', 'status', 'confirmation', 'job_id', 'last_submission_error')}
            if item.get('job_id'):
                job = self.get_job(item['job_id'])
                if job and job.owner_user_id == self.request.owner and job.course_id == self.request.course_id:
                    state['task_status'] = str(getattr(job.status, 'value', job.status))
            states.append(state)
        return {'course_catalog': [item.model_dump() for item in catalog],
                'working_memory': self.session.data.get('working_memory', {}),
                'discussion_workspace': self.session.data.get('discussion_workspace'),
                'report_states': states}

    def select_workspace(self, args):
        from app.chat.application.knowledge_context import ResolvedWorkspaceContext, knowledge_candidates
        if not self.request.course_id or not self.course_storage:
            raise ValueError('course_required')
        catalog = knowledge_candidates(self.course_storage.get_knowledge_graph(self.request.course_id))
        course = self.course_storage.get_course_info(self.request.course_id) or {}
        title = str(course.get('name') or course.get('title') or self.request.course_id)
        context = ResolvedWorkspaceContext(course_id=self.request.course_id, course_title=title,
            scope_type=args.scope_type, scope_id=args.scope_id, scope_title=title,
            scope_path=[title], resolution='resolved', explicit_course=args.scope_type == 'course')
        if args.scope_type == 'knowledge_point':
            node = next((item for item in catalog if item.scope_id == args.scope_id), None)
            if node is None:
                raise ValueError('knowledge_point_not_in_course')
            context.scope_title, context.scope_path = node.scope_title, node.scope_path
        elif args.scope_id:
            raise ValueError('course_scope_has_no_node_id')
        context.update_workspace = (args.scope_type, args.scope_id) != (self.request.scope_type or 'course', self.request.scope_id)
        # Keep a prior change signal when the model selects the same node twice.
        context.update_workspace |= bool(self.request.workspace_context and self.request.workspace_context.update_workspace)
        self.request.scope_type, self.request.scope_id = args.scope_type, args.scope_id
        self.request.workspace_context = context
        self.session.data['discussion_workspace'] = {**context.model_dump(), 'topic': args.topic}
        self.session.save()
        return self.session.data['discussion_workspace']

    def update_working_memory(self, args):
        data = {**args.model_dump(), 'source_request_id': self.request.request_id,
                'source_user_message': self.request.question, 'interpreted_by': 'model'}
        self.session.data['working_memory'] = data
        self.session.save()
        return data
