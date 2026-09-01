"""
Authentication API routes.
"""

import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserInfoResponse,
    UserProfileUpdateRequest,
)
from core.config import Config
from core.auth import auth_manager
from core.user_storage import user_storage
from app.services.course_membership_bootstrap import get_course_membership_bootstrap

router = APIRouter(prefix="/api/auth", tags=["认证"])
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    token = credentials.credentials
    return auth_manager.get_current_user(token)


@router.post("/login", response_model=LoginResponse, summary="User login")
async def login(request: LoginRequest):
    if not user_storage.verify_password(request.username, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    user = user_storage.get_user(request.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    token = auth_manager.create_token(
        username=user["username"],
        role=user.get("role", "student"),
    )

    return LoginResponse(
        token=token,
        user={
            "username": user["username"],
            "role": user.get("role", "student"),
        },
    )


@router.post("/register", response_model=LoginResponse, summary="User register")
async def register(request: RegisterRequest):
    # Public registration must never grant the system-admin role.
    valid_roles = ["teacher", "student"]
    if request.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Valid roles: {', '.join(valid_roles)}",
        )

    try:
        user = user_storage.create_user(
            username=request.username,
            password=request.password,
            role=request.role,
        )

        get_course_membership_bootstrap().on_user_created(user)

        token = auth_manager.create_token(
            username=user["username"],
            role=user["role"],
        )

        return LoginResponse(
            token=token,
            user={
                "username": user["username"],
                "role": user["role"],
            },
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get("/me", response_model=UserInfoResponse, summary="Current user")
async def get_me(current_user: dict = Depends(get_current_user)):
    user = user_storage.get_user(current_user["username"])
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserInfoResponse(**user_storage.public_user(user))


@router.put("/me", response_model=UserInfoResponse, summary="Update current profile")
async def update_me(
    request: UserProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    updated = user_storage.update_user(
        current_user["username"], **request.model_dump()
    )
    if not updated:
        raise HTTPException(status_code=404, detail="用户不存在")
    user = user_storage.get_user(current_user["username"])
    return UserInfoResponse(**user_storage.public_user(user))


@router.post("/change-password", summary="Change current password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    if request.current_password == request.new_password:
        raise HTTPException(status_code=422, detail="新密码不能与当前密码相同")
    if not user_storage.change_password(
        current_user["username"],
        current_password=request.current_password,
        new_password=request.new_password,
    ):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    return {"changed": True}


@router.post("/avatar", response_model=UserInfoResponse, summary="Upload current avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    content_type = str(file.content_type or "").lower()
    suffix_by_type = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    if content_type not in suffix_by_type:
        raise HTTPException(status_code=400, detail="头像仅支持 JPG、PNG 或 WebP")
    data = await file.read(2 * 1024 * 1024 + 1)
    await file.close()
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="头像文件不能超过 2MB")
    if not data:
        raise HTTPException(status_code=400, detail="头像文件为空")
    avatar_dir = Config.STORAGE_ROOT / "profile_avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    owner_hash = hashlib.sha256(current_user["username"].encode("utf-8")).hexdigest()[:24]
    destination = avatar_dir / f"{owner_hash}{suffix_by_type[content_type]}"
    temporary = destination.with_suffix(f"{destination.suffix}.tmp")
    temporary.write_bytes(data)
    temporary.replace(destination)
    user_storage.update_user(current_user["username"], avatar_path=str(destination))
    user = user_storage.get_user(current_user["username"])
    return UserInfoResponse(**user_storage.public_user(user))


@router.get("/avatar", summary="Current avatar")
async def get_avatar(current_user: dict = Depends(get_current_user)):
    user = user_storage.get_user(current_user["username"])
    path = Path(str((user or {}).get("avatar_path") or ""))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="尚未设置头像")
    return FileResponse(path)


@router.post("/verify", summary="Verify token")
async def verify_token(current_user: dict = Depends(get_current_user)):
    return {
        "valid": True,
        "user": current_user,
    }
