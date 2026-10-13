"""Course identity from the authorized directory, never inferred from prose."""
from fastapi import HTTPException


def learning_orientation(room, topic_id):
    chapters = room['chapters']
    index = next((i for i, chapter in enumerate(chapters) if chapter['id'] == topic_id), None)
    if index is None:
        raise HTTPException(404, '知识点不存在或无权访问')
    chapter = chapters[index]
    objectives = chapter.get('objectives') or []
    # Core orientation stays bounded even when a generated route is verbose.
    # Preserve objective identifiers for checks; never invent missing targets.
    compact_objectives = [
        {'objective_id': item.get('objective_id'), 'text': str(item.get('text', ''))[:180]}
        if isinstance(item, dict) else {'text': str(item)[:180]}
        for item in objectives[:3]
    ]
    return {
        'source': 'authorized_course_directory',
        'course': {'id': room['id'], 'title': room['title']},
        'current_topic': {'id': chapter['id'], 'title': chapter['title'],
                          'position': index + 1, 'total_topics': len(chapters),
                          'objectives': compact_objectives,
                          'objectives_truncated': len(objectives) > 3 or any(
                              len(str(item.get('text', '') if isinstance(item, dict) else item)) > 180
                              for item in objectives[:3])},
        'route_version': room.get('routeVersion'),
    }


def learning_route_details(room, topic_id):
    chapters = room['chapters']
    index = next(i for i, chapter in enumerate(chapters) if chapter['id'] == topic_id)
    # Optional supporting context; long routes must not displace the current
    # course/topic identity, the user's selection, or their question.
    nearby = chapters[max(0, index - 2):index + 3]
    return {
        'nearby_topics': [{'id': chapter['id'], 'title': chapter['title']} for chapter in nearby],
        'outline_is_partial': len(nearby) < len(chapters),
    }
