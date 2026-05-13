"""
用户数据存储模块
使用JSON文件存储用户信息（生产环境建议使用数据库）
"""
import os
import json
import hashlib
from typing import Optional, Dict, List
from datetime import datetime
from pathlib import Path


class UserStorage:
    """用户存储管理类"""
    
    def __init__(self, storage_file: str = "storage/users.json"):
        """
        初始化用户存储
        
        Args:
            storage_file: 用户数据存储文件路径
        """
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_default_user()
    
    def _ensure_default_user(self):
        """确保存在默认用户"""
        users = self._load_users()
        existing_usernames = {user.get("username") for user in users}
        
        default_users = [
            {
                "username": "admin",
                "password_hash": self._hash_password("admin123"),
                "created_at": datetime.now().isoformat(),
                "role": "admin"
            },
            {
                "username": "teacher",
                "password_hash": self._hash_password("teacher123"),
                "created_at": datetime.now().isoformat(),
                "role": "teacher"
            },
            {
                "username": "student",
                "password_hash": self._hash_password("student123"),
                "created_at": datetime.now().isoformat(),
                "role": "student"
            }
        ]
        
        # 只添加不存在的默认用户
        need_save = False
        for default_user in default_users:
            if default_user["username"] not in existing_usernames:
                users.append(default_user)
                need_save = True
        
        if need_save:
            self._save_users(users)
    
    def _hash_password(self, password: str) -> str:
        """
        对密码进行哈希处理
        
        Args:
            password: 明文密码
            
        Returns:
            哈希后的密码
        """
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    def _load_users(self) -> List[Dict]:
        """加载用户数据"""
        if not self.storage_file.exists():
            return []
        
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("users", [])
        except (json.JSONDecodeError, IOError):
            return []
    
    def _save_users(self, users: List[Dict]):
        """保存用户数据"""
        data = {"users": users}
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            raise Exception(f"保存用户数据失败: {str(e)}")
    
    def get_user(self, username: str) -> Optional[Dict]:
        """
        根据用户名获取用户信息
        
        Args:
            username: 用户名
            
        Returns:
            用户信息字典，如果不存在返回None
        """
        users = self._load_users()
        for user in users:
            if user.get("username") == username:
                return user.copy()
        return None
    
    def verify_password(self, username: str, password: str) -> bool:
        """
        验证用户名和密码
        
        Args:
            username: 用户名
            password: 明文密码
            
        Returns:
            验证是否通过
        """
        user = self.get_user(username)
        if not user:
            return False
        
        password_hash = self._hash_password(password)
        return user.get("password_hash") == password_hash
    
    def create_user(self, username: str, password: str, role: str = "student") -> Dict:
        """
        创建新用户
        
        Args:
            username: 用户名
            password: 明文密码
            role: 用户角色（admin, teacher, student）
            
        Returns:
            创建的用户信息
            
        Raises:
            ValueError: 如果用户名已存在
        """
        if self.get_user(username):
            raise ValueError(f"用户名 {username} 已存在")
        
        users = self._load_users()
        new_user = {
            "username": username,
            "password_hash": self._hash_password(password),
            "created_at": datetime.now().isoformat(),
            "role": role
        }
        users.append(new_user)
        self._save_users(users)
        
        # 返回用户信息（不包含密码哈希）
        return {
            "username": new_user["username"],
            "role": new_user["role"],
            "created_at": new_user["created_at"]
        }
    
    def update_user(self, username: str, **kwargs) -> Optional[Dict]:
        """
        更新用户信息
        
        Args:
            username: 用户名
            **kwargs: 要更新的字段（如 password, role）
            
        Returns:
            更新后的用户信息，如果用户不存在返回None
        """
        users = self._load_users()
        user_found = False
        
        for user in users:
            if user.get("username") == username:
                if "password" in kwargs:
                    user["password_hash"] = self._hash_password(kwargs["password"])
                if "role" in kwargs:
                    user["role"] = kwargs["role"]
                user_found = True
                break
        
        if not user_found:
            return None
        
        self._save_users(users)
        updated_user = self.get_user(username)
        if updated_user:
            # 移除密码哈希
            updated_user.pop("password_hash", None)
        return updated_user
    
    def list_users(self) -> List[Dict]:
        """
        列出所有用户（不包含密码哈希）
        
        Returns:
            用户列表
        """
        users = self._load_users()
        return [
            {
                "username": user.get("username"),
                "role": user.get("role"),
                "created_at": user.get("created_at")
            }
            for user in users
        ]


# 全局用户存储实例
user_storage = UserStorage()

