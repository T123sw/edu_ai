from .edit import canvas_create, canvas_edit, canvas_view_all, canvas_view_re, canvas_save, canvas_load

canvas_tools = [
    canvas_create,
    canvas_view_re,
    canvas_view_all,
    canvas_save,
    canvas_edit,
    canvas_load,
]

__all__ = [
    'canvas_tools'
]