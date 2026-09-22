"""The course classroom switch is authoritative over model-inferred formats."""


def course_resource_types(request, inferred=()):
    kinds = list(dict.fromkeys(['report', 'quiz', *request.overrides.required_resource_types, *inferred]))
    if request.operation == 'create_course':
        kinds = [kind for kind in kinds if kind != 'classroom']
        if request.overrides.include_classroom:
            kinds.append('classroom')
    return kinds
