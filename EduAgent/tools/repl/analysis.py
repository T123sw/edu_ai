from langchain_core.tools import tool

# 全局执行环境，跨多次调用共享
REPL_ENV = {}


@tool
def repl(code: str) -> dict:
    """
    在用户主机的 env 中执行 Python 代码（最后一表达式会回显）。
    可以使用此工具操纵用户电脑，使用用户资源，扩展能力边界。
    :param code: 要执行的代码（可含 ```python ... ``` 或缩进）
    :return: {'ok': True, 'result': '<stdout+stderr+最后值>'}
             或 {'ok': False, 'error': '...'} / {'ok': False, 'permit': '用户不同意'}
    """
    import io, re, ast, textwrap
    from contextlib import redirect_stdout, redirect_stderr

    global REPL_ENV

    # ---- 交互确认 ----
    print(code)
    try:
        permit = input("是否允许模型操作？(回车=允许，N/n=拒绝)：").strip().lower()
    except EOFError:
        # 在无 stdin 环境下避免直接炸
        return {"ok": False, "error": "无法读取用户输入（无标准输入环境）"}
    if permit.startswith("n"):
        advice = input("给模型的建议：")
        return {"ok": False, "permit": "用户不同意", "user_advice": advice}

    # ---- 代码提取与规范化 ----
    def extract_code(txt: str) -> str:
        m = re.search(r"```(?:python)?\s*(.*?)```", txt, re.S | re.I)
        return m.group(1) if m else txt

    def normalize(txt: str) -> str:
        txt = txt.replace("\u00A0", " ").replace("\u3000", " ")  # NBSP/全角空格
        txt = txt.replace("\t", "    ")
        txt = textwrap.dedent(txt)
        return txt.strip()

    raw = extract_code(code)
    code_norm = normalize(raw)
    if not code_norm:
        return {"ok": False, "error": "空代码"}

    # ---- 预解析：判断是否以表达式结尾 ----
    try:
        mod = ast.parse(code_norm, mode="exec")
    except SyntaxError as e:
        return {"ok": False, "error": f"SyntaxError: {e}"}

    body = mod.body
    last_is_expr = bool(body and isinstance(body[-1], ast.Expr))

    # ---- 编译：主体（可能去掉最后表达式） + 最后表达式（可选） ----
    stmts_code_obj = None
    expr_code_obj = None
    if last_is_expr:
        # 主体 = 除去最后表达式
        if len(body) > 1:
            stmts_module = ast.Module(body=body[:-1], type_ignores=[])
            stmts_code_obj = compile(stmts_module, "<repl>", "exec")
        expr = ast.Expression(body=body[-1].value)
        expr_code_obj = compile(expr, "<repl-expr>", "eval")
    else:
        stmts_code_obj = compile(mod, "<repl>", "exec")

    # 确保有内建函数
    if "__builtins__" not in REPL_ENV:
        import builtins
        REPL_ENV["__builtins__"] = builtins

    # ---- 执行并捕获输出 ----
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            if stmts_code_obj is not None:
                exec(stmts_code_obj, REPL_ENV, REPL_ENV)
            if expr_code_obj is not None:
                val = eval(expr_code_obj, REPL_ENV, REPL_ENV)
                if val is not None:
                    print(val)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    result = out.getvalue() + err.getvalue()

    return {"ok": True, "result": result}
