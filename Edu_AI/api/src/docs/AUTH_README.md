# 认证功能说明

## 概述

已实现完整的用户认证系统，包括：
- 用户登录
- 用户注册
- JWT token生成和验证
- 用户信息获取

## 默认用户

系统初始化时会自动创建以下默认用户：

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | admin |
| teacher | teacher123 | teacher |
| student | student123 | student |

## API 接口

### 1. 用户登录

**接口**: `POST /api/auth/login`

**请求体**:
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**响应**:
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "username": "admin",
    "role": "admin"
  }
}
```

### 2. 用户注册

**接口**: `POST /api/auth/register`

**请求体**:
```json
{
  "username": "newuser",
  "password": "password123",
  "role": "student"  // 可选，默认为 "student"
}
```

**响应**:
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "username": "newuser",
    "role": "student"
  }
}
```

### 3. 获取当前用户信息

**接口**: `GET /api/auth/me`

**请求头**:
```
Authorization: Bearer <token>
```

**响应**:
```json
{
  "username": "admin",
  "role": "admin"
}
```

### 4. 验证token

**接口**: `POST /api/auth/verify`

**请求头**:
```
Authorization: Bearer <token>
```

**响应**:
```json
{
  "valid": true,
  "user": {
    "username": "admin",
    "role": "admin"
  }
}
```

## 数据存储

- 用户数据存储在 `storage/users.json` 文件中
- 密码使用 SHA256 哈希存储
- 生产环境建议使用数据库（如 PostgreSQL、MySQL）

## JWT Token

- Token 有效期：24小时
- 算法：HS256
- Secret Key：可通过环境变量 `JWT_SECRET_KEY` 配置（默认：`edu-ai-secret-key-change-in-production`）

**生产环境注意事项**：
1. 必须修改 `JWT_SECRET_KEY` 为强随机字符串
2. 建议使用环境变量或密钥管理服务
3. 考虑使用数据库替代 JSON 文件存储用户数据

## 前端集成

前端已更新 `src/services/auth.ts`，现在会调用真实的后端API。

**使用示例**:
```typescript
import { login, register, getCurrentUser } from './services/auth';

// 登录
const response = await login('admin', 'admin123');
console.log(response.token); // JWT token
console.log(response.user); // 用户信息

// 注册
const registerResponse = await register('newuser', 'password123', 'student');

// 获取当前用户（需要token）
const user = await getCurrentUser(token);
```

## 安装依赖

在安装新的依赖包后，需要重新安装：

```bash
pip install -r requirements_api.txt
```

新增的依赖：
- `pyjwt>=2.8.0` - JWT token生成和验证
- `python-jose[cryptography]>=3.3.0` - JWT工具（可选）

## 测试

可以使用 curl 或 Postman 测试API：

```bash
# 登录
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 获取用户信息（需要替换为实际的token）
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <your-token>"
```

## 安全建议

1. **密码策略**：建议实现密码复杂度要求（长度、字符类型等）
2. **Token刷新**：考虑实现 refresh token 机制
3. **HTTPS**：生产环境必须使用 HTTPS
4. **CORS配置**：限制允许的源域名
5. **速率限制**：实现登录尝试次数限制，防止暴力破解
6. **密码重置**：实现密码重置功能
7. **双因素认证**：对于敏感账户，考虑实现2FA

## 文件结构

```
api/Edu_AI/
├── core/
│   ├── user_storage.py    # 用户数据存储管理
│   └── auth.py            # JWT认证管理
├── app/
│   ├── auth.py            # 认证API路由
│   └── main.py           # 主应用（已集成认证路由）
└── storage/
    └── users.json         # 用户数据文件（自动创建）
```

