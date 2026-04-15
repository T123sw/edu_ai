# 文件路径: app/auth.py
async def get_current_user():
    """伪造一个默认的登录用户，方便我们在本地测试"""
    return {"username": "admin"}