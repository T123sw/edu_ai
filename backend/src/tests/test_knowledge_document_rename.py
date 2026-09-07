import pytest
from course_api_test_support import CourseApiTestFactory


@pytest.fixture
def course_api(tmp_path, monkeypatch):
    for mode in ['COURSE_PERSISTENCE_MODE', 'COURSE_MEMBERSHIP_PERSISTENCE_MODE', 'KNOWLEDGE_PERSISTENCE_MODE', 'APP_STATE_PERSISTENCE_MODE', 'MATERIAL_PERSISTENCE_MODE']:
        monkeypatch.setenv(mode, 'json')
    factory = CourseApiTestFactory(tmp_path, monkeypatch)
    factory.manager.save_knowledge_base_index('course-1', [{
        'id': 'doc-rename', 'filename': 'original.md', 'source_title': '原名称',
        'path': 'knowledge_base/documents/original.md', 'status': 'ready',
        'library_type': 'course', 'rag_index_key': 'stable-source-key',
        'created_at': '2026-09-07T00:00:00Z', 'chunk_count': 12,
    }])
    return factory


def test_rename_persists_title_without_changing_source_or_file(course_api):
    client = course_api.client_for('teacher-a', 'teacher')
    path = '/api/courses/course-1/knowledge-base/documents/doc-rename'
    response = client.patch(path, json={'name': '  链表学习资料  '})
    assert response.status_code == 200
    assert client.get(path).json()['display_name'] == '链表学习资料'
    record = course_api.manager.get_knowledge_base_index('course-1')[0]
    assert record['filename'] == 'original.md'
    assert record['rag_index_key'] == 'stable-source-key'
    assert record['path'] == 'knowledge_base/documents/original.md'
    assert record['chunk_count'] == 12


def test_rename_rejects_viewer_and_blank_name(course_api):
    path = '/api/courses/course-1/knowledge-base/documents/doc-rename'
    assert course_api.client_for('student-a', 'student').patch(path, json={'name': '新名称'}).status_code == 403
    assert course_api.client_for('teacher-a', 'teacher').patch(path, json={'name': '   '}).status_code == 422
    assert course_api.manager.get_knowledge_base_index('course-1')[0]['source_title'] == '原名称'
