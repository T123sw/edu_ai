"""Every newly generated course node includes a report and a quiz."""


def course_resource_types(request, inferred=()):
    kinds = list(dict.fromkeys([*request.overrides.required_resource_types, *inferred]))
    if request.operation in ('create_course', 'adjust_course'):
        kinds = list(dict.fromkeys(['report', 'quiz', *kinds]))
        kinds = [kind for kind in kinds if kind != 'classroom']
        if request.overrides.include_classroom:
            kinds.append('classroom')
    # Supplements and revisions keep their explicitly requested resource scope.
    return kinds
