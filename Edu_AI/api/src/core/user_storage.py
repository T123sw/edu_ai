"""
用户数据存储模块
使用JSON文件存储用户信息（生产环境建议使用数据库）
"""
import os
import json
import hashlib
import hmac
import secrets
import threading
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
        self._lock = threading.RLock()
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
        iterations = 260_000
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("ascii"), iterations
        ).hex()
        return f"pbkdf2_sha256${iterations}${salt}${digest}"

    @staticmethod
    def _verify_password_hash(password: str, stored_hash: str) -> bool:
        if stored_hash.startswith("pbkdf2_sha256$"):
            try:
                _, raw_iterations, salt, expected = stored_hash.split("$", 3)
                actual = hashlib.pbkdf2_hmac(
                    "sha256",
                    password.encode("utf-8"),
                    salt.encode("ascii"),
                    int(raw_iterations),
                ).hex()
                return hmac.compare_digest(actual, expected)
            except (TypeError, ValueError):
                return False
        # Compatibility with legacy unsalted SHA-256 records; upgraded on login.
        legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy, str(stored_hash or ""))
    
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
        temporary = self.storage_file.with_name(
            f".{self.storage_file.name}.{secrets.token_hex(8)}.tmp"
        )
        try:
            with temporary.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, self.storage_file)
        except IOError as e:
            raise Exception(f"保存用户数据失败: {str(e)}")
        finally:
            temporary.unlink(missing_ok=True)
    
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
        
        valid = self._verify_password_hash(password, str(user.get("password_hash") or ""))
        if valid and not str(user.get("password_hash") or "").startswith("pbkdf2_sha256$"):
            with self._lock:
                users = self._load_users()
                for item in users:
                    if item.get("username") == username:
                        item["password_hash"] = self._hash_password(password)
                        break
                self._save_users(users)
        return valid
    
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
        
        with self._lock:
            users = self._load_users()
            new_user = {
                "username": username,
                "password_hash": self._hash_password(password),
                "created_at": datetime.now().isoformat(),
                "role": role,
                "display_name": username,
                "email": "",
                "phone": "",
                "department": "",
                "bio": "",
                "avatar_path": "",
                "password_updated_at": "",
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
        with self._lock:
            users = self._load_users()
            user_found = False
            allowed_profile_fields = {
                "display_name",
                "email",
                "phone",
                "department",
                "bio",
                "avatar_path",
            }
            for user in users:
                if user.get("username") == username:
                    if "password" in kwargs:
                        user["password_hash"] = self._hash_password(kwargs["password"])
                        user["password_updated_at"] = datetime.now().isoformat()
                    if "role" in kwargs:
                        user["role"] = kwargs["role"]
                    for field in allowed_profile_fields:
                        if field in kwargs:
                            user[field] = str(kwargs[field] or "")
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

    def change_password(
        self, username: str, *, current_password: str, new_password: str
    ) -> bool:
        if not self.verify_password(username, current_password):
            return False
        self.update_user(username, password=new_password)
        return True

    @staticmethod
    def public_user(user: Dict) -> Dict:
        value = dict(user)
        value.pop("password_hash", None)
        value.pop("avatar_path", None)
        value.setdefault("display_name", value.get("username", ""))
        for field in (
            "email",
            "phone",
            "department",
            "bio",
            "created_at",
            "password_updated_at",
        ):
            value.setdefault(field, "")
        value["avatar_url"] = "/api/auth/avatar" if user.get("avatar_path") else ""
        return value
    
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

