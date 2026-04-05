"""
认证API路由
提供登录、注册、用户信息等接口
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from core.user_storage import user_storage
from core.auth import auth_manager

router = APIRouter(prefix="/api/auth", tags=["认证"])
security = HTTPBearer()


class LoginRequest(BaseModel):
    """登录请求模型"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class RegisterRequest(BaseModel):
    """注册请求模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名（3-50个字符）")
    password: str = Field(..., min_length=6, max_length=100, description="密码（至少6个字符）")
    role: Optional[str] = Field(default="student", description="用户角色（admin, teacher, student）")


class LoginResponse(BaseModel):
    """登录响应模型"""
    token: str = Field(..., description="JWT token")
    user: dict = Field(..., description="用户信息")


class UserInfoResponse(BaseModel):
    """用户信息响应模型"""
    username: str
    role: str


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    从请求头中获取当前用户（依赖注入）
    
    Args:
        credentials: HTTP Bearer token凭证
        
    Returns:
        用户信息字典
    """
    token = credentials.credentials
    return auth_manager.get_current_user(token)


@router.post("/login", response_model=LoginResponse, summary="用户登录")
async def login(request: LoginRequest):
    """
    用户登录接口
    
    - **username**: 用户名
    - **password**: 密码
    
    返回JWT token和用户信息
    """
    # 验证用户名和密码
    if not user_storage.verify_password(request.username, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    # 获取用户信息
    user = user_storage.get_user(request.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 生成token
    token = auth_manager.create_token(
        username=user["username"],
        role=user.get("role", "student")
    )
    
    # 返回响应（不包含密码哈希）
    return LoginResponse(
        token=token,
        user={
            "username": user["username"],
            "role": user.get("role", "student")
        }
    )


@router.post("/register", response_model=LoginResponse, summary="用户注册")
async def register(request: RegisterRequest):
    """
    用户注册接口
    
    - **username**: 用户名（3-50个字符）
    - **password**: 密码（至少6个字符）
    - **role**: 用户角色（可选，默认为student）
    
    注册成功后自动登录，返回JWT token和用户信息
    """
    # 验证角色
    valid_roles = ["admin", "teacher", "student"]
    if request.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的角色，必须是以下之一: {', '.join(valid_roles)}"
        )
    
    try:
        # 创建用户
        user = user_storage.create_user(
            username=request.username,
            password=request.password,
            role=request.role
        )
        
        # 生成token
        token = auth_manager.create_token(
            username=user["username"],
            role=user["role"]
        )
        
        # 返回响应
        return LoginResponse(
            token=token,
            user={
                "username": user["username"],
                "role": user["role"]
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/me", response_model=UserInfoResponse, summary="获取当前用户信息")
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    获取当前登录用户的信息
    
    需要在请求头中携带有效的JWT token:
    ```
    Authorization: Bearer <token>
    ```
    """
    return UserInfoResponse(
        username=current_user["username"],
        role=current_user["role"]
    )


@router.post("/verify", summary="验证token")
async def verify_token(current_user: dict = Depends(get_current_user)):
    """
    验证token是否有效
    
    如果token有效，返回用户信息；如果无效或过期，返回401错误
    """
    return {
        "valid": True,
        "user": current_user
    }

