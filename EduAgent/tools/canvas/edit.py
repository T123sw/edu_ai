from pathlib import Path
from typing import Literal

from langchain_core.tools import tool

from .types import Canvas, canvas_type
import re

# 全局 canvas 列表
canvas_list: list[Canvas] = []

# 编辑操作类型
operation_type = Literal['append', 'insert', 'replace', 'replace_all', 'delete']


@tool
def canvas_create(type: canvas_type, name: str) -> bool:
    """
    创建可编辑画布
    :param type: 画布类别
    :param name: 画布名称（在当前会话中唯一）
    :return: 是否创建成功
    """
    canvas = Canvas()
    canvas.content = ''
    canvas.type = type
    canvas.name = name
    canvas_list.append(canvas)
    return True


@tool
def canvas_all() -> list:
    """
    返回现在有几个canvas
    :return: 所有canvas的type和name列表
    """
    return [{'name': x.name, 'type': x.type} for x in canvas_list]


@tool
def canvas_edit(name: str, pattern: str, content: str, operation: operation_type) -> bool | str:
    """
    编辑canvas，使用正则的模式匹配找到pattern，基于此编辑canvas。

    canvas内容为''的时候，pattern传''即可（此时建议选用简单的 replace 操作整体替换）。
    为了方便匹配，每次写画布中的内容应该在内容前后添加不影响文件的标记，例如：
    在 C 代码中使用注释 // BEGIN [XX] ... // END [XX] 来标记一段代码，有助于后续找到此部分。

    :param name: 指定canvas的名称
    :param pattern: 正则模式匹配（需是合法的 Python 正则表达式）
    :param content: 你要编辑的内容
    :param operation: append|insert|replace|replace_all|delete
        - append：在匹配到的内容后面追加
        - insert：在匹配到的内容之前追加
        - replace：替换第一个匹配到的内容
        - replace_all：替换所有匹配到的内容
        - delete：删除第一个匹配到的内容
    :return: 操作是否成功。若返回 str 类型则说明正则或匹配有问题（请据此自行调整）
    """
    # 找到对应 canvas
    canvas = None
    for c in canvas_list:
        if c.name == name:
            canvas = c
            break

    if canvas is None:
        return f"未找到名为 {name!r} 的 canvas。"

    # 先编译正则，避免非法 pattern 直接把整个流程搞崩
    try:
        regex = re.compile(pattern, re.S)
    except re.error as e:
        return (
            f"正则表达式错误: {e}. "
            "请修改 pattern（不能以 *, +, ?, { 等量词开头；如需匹配字面星号请使用 \\*）。"
        )

    match = regex.search(canvas.content)
    if match is None:
        return "正则匹配失败：在当前 canvas 中未找到 pattern 对应内容。"

    # 实际编辑操作
    if operation == 'delete':
        canvas.content, _ = regex.subn('', canvas.content, count=1)
        return True

    if operation == 'append':
        # 在匹配内容之后追加
        def _append(m: re.Match) -> str:
            return m.group(0) + content

        canvas.content, _ = regex.subn(_append, canvas.content, count=1)
        return True

    if operation == 'insert':
        # 在匹配内容之前插入
        def _insert(m: re.Match) -> str:
            return content + m.group(0)

        canvas.content, _ = regex.subn(_insert, canvas.content, count=1)
        return True

    if operation == 'replace':
        canvas.content, _ = regex.subn(content, canvas.content, count=1)
        return True

    if operation == 'replace_all':
        canvas.content, _ = regex.subn(content, canvas.content)
        return True

    # 理论上不会走到这里
    return f"未知 operation: {operation}"


@tool
def canvas_view_all(name: str) -> str:
    """
    查看整个canvas（并非行号）
    :param name: canvas的名称
    :return: canvas中的内容；若未找到则返回提示信息
    """
    canvas = None
    for c in canvas_list:
        if c.name == name:
            canvas = c
            break

    if canvas is None:
        return f"未找到名为 {name!r} 的 canvas。"

    return canvas.content


@tool
def canvas_view_re(name: str, pattern: str) -> str:
    """
    使用正则匹配的方式预览canvas中的内容
    :param name: 指定canvas的name
    :param pattern: 正则匹配模式
    :return: search到的字符串；若未匹配到或正则错误则返回提示信息
    """
    canvas = None
    for c in canvas_list:
        if c.name == name:
            canvas = c
            break

    if canvas is None:
        return f"未找到名为 {name!r} 的 canvas。"

    try:
        regex = re.compile(pattern, re.S)
    except re.error as e:
        return f"正则表达式错误: {e}"

    match = regex.search(canvas.content)
    if match is None:
        return 'None，未匹配到'
    return match.group(0)


@tool
def canvas_save(name: str, path: str) -> bool | str:
    """
    将canvas保存到具体的地址
    :param name: 你要保存的canvas
    :param path: /XX/XX/name.type（绝对地址）
    :return: 存放成功会返回 True；失败返回 False 或错误信息字符串
    """
    print(path)
    canvas = None
    for c in canvas_list:
        if c.name == name:
            canvas = c
            break

    if canvas is None:
        return f"未找到名为 {name!r} 的 canvas。"

    file_path = Path(path)
    try:
        # 确保父目录存在（可选）
        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)

        with file_path.open('w', encoding='utf-8') as f:
            f.write(canvas.content)
    except FileNotFoundError:
        return False
    except OSError as e:
        return f"写入文件失败: {e}"

    return True


@tool
def canvas_load(name: str, type: canvas_type, file: str) -> bool | str:
    """
    将某一个文件打开为canvas
    :param name: canvas的命名
    :param type: canvas的类别
    :param file: 文件具体地址
    :return: 是否打开成功；若失败返回 False 或错误信息字符串
    """
    file_path = Path(file)
    if not file_path.exists():
        return False

    canvas = Canvas()
    canvas.type = type
    canvas.name = name
    try:
        with file_path.open('r', encoding='utf-8') as f:
            canvas.content = f.read()
    except OSError as e:
        return f"读取文件失败: {e}"

    canvas_list.append(canvas)
    return True
