"""
认证模块
提供JWT token生成和验证功能
"""
import os
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import HTTPException, status


class AuthManager:
    """认证管理器"""
    
    def __init__(self, secret_key: Optional[str] = None, algorithm: str = "HS256"):
        """
        初始化认证管理器
        
        Args:
            secret_key: JWT密钥，如果为None则使用默认密钥（生产环境应使用环境变量）
            algorithm: JWT算法
        """
        self.secret_key = secret_key or os.getenv("JWT_SECRET_KEY", "edu-ai-secret-key-change-in-production")
        self.algorithm = algorithm
        self.token_expire_hours = 24  # token过期时间（小时）
    
    def create_token(self, username: str, role: str = "student") -> str:
        """
        创建JWT token
        
        Args:
            username: 用户名
            role: 用户角色
            
        Returns:
            JWT token字符串
        """
        expire = datetime.utcnow() + timedelta(hours=self.token_expire_hours)
        payload = {
            "username": username,
            "role": role,
            "exp": expire,
            "iat": datetime.utcnow()
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    def verify_token(self, token: str) -> Dict:
        """
        验证JWT token
        
        Args:
            token: JWT token字符串
            
        Returns:
            token中的payload（包含username和role）
            
        Raises:
            HTTPException: 如果token无效或已过期
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token已过期"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的token"
            )
    
    def get_current_user(self, token: str) -> Dict:
        """
        从token中获取当前用户信息
        
        Args:
            token: JWT token字符串
            
        Returns:
            用户信息字典
        """
        payload = self.verify_token(token)
        return {
            "username": payload.get("username"),
            "role": payload.get("role")
        }


# 全局认证管理器实例
auth_manager = AuthManager()

