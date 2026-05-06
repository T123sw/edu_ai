"""
Authentication API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, UserInfoResponse
from core.auth import auth_manager
from core.user_storage import user_storage

router = APIRouter(prefix="/api/auth", tags=["认证"])
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
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
    valid_roles = ["admin", "teacher", "student"]
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
    return UserInfoResponse(
        username=current_user["username"],
        role=current_user["role"],
    )


@router.post("/verify", summary="Verify token")
async def verify_token(current_user: dict = Depends(get_current_user)):
    return {
        "valid": True,
        "user": current_user,
    }
