"""Retired per-page model mapping; saved historical bindings remain readable."""


def map_native_pages(*args, **kwargs):
    raise RuntimeError('OPENMAIC_PAGE_MAPPING_RETIRED: HyperFrames imports its native timeline')
