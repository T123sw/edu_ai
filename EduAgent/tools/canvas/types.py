from typing import Literal

from pydantic import BaseModel

canvas_type = Literal['html', 'python', 'javascript', 'css', 'c/c++', 'markdown', 'docx']

class Canvas(BaseModel):
    content: str = ""
    type: canvas_type = None
    name: str = ""