"""
测试认证功能
用于验证登录API是否正常工作
"""
import requests
import json

API_BASE_URL = "http://localhost:8000"

def test_login():
    """测试登录接口"""
    print("=" * 50)
    print("测试登录接口")
    print("=" * 50)
    
    # 测试默认管理员登录
    print("\n1. 测试管理员登录 (admin/admin123)...")
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/auth/login",
            json={
                "username": "admin",
                "password": "admin123"
            },
            timeout=5
        )
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 登录成功!")
            print(f"  Token: {data['token'][:50]}...")
            print(f"  用户: {data['user']}")
            return True
        else:
            print(f"✗ 登录失败: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到服务器，请确保后端服务已启动")
        print(f"  尝试连接: {API_BASE_URL}")
        return False
    except requests.exceptions.Timeout:
        print("✗ 请求超时")
        return False
    except Exception as e:
        print(f"✗ 发生错误: {str(e)}")
        return False

def test_register():
    """测试注册接口"""
    print("\n" + "=" * 50)
    print("测试注册接口")
    print("=" * 50)
    
    import random
    test_username = f"testuser_{random.randint(1000, 9999)}"
    
    print(f"\n1. 测试注册新用户 ({test_username})...")
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/auth/register",
            json={
                "username": test_username,
                "password": "test123456",
                "role": "student"
            },
            timeout=5
        )
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 注册成功!")
            print(f"  Token: {data['token'][:50]}...")
            print(f"  用户: {data['user']}")
            return True
        else:
            print(f"✗ 注册失败: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到服务器，请确保后端服务已启动")
        return False
    except Exception as e:
        print(f"✗ 发生错误: {str(e)}")
        return False

def test_get_me(token):
    """测试获取用户信息接口"""
    print("\n" + "=" * 50)
    print("测试获取用户信息接口")
    print("=" * 50)
    
    print("\n1. 测试获取当前用户信息...")
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/auth/me",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=5
        )
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 获取成功!")
            print(f"  用户信息: {data}")
            return True
        else:
            print(f"✗ 获取失败: {response.text}")
            return False
    except Exception as e:
        print(f"✗ 发生错误: {str(e)}")
        return False

if __name__ == "__main__":
    print("\n开始测试认证功能...\n")
    
    # 测试登录
    login_success = test_login()
    
    if login_success:
        # 获取token用于后续测试
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/auth/login",
                json={"username": "admin", "password": "admin123"},
                timeout=5
            )
            if response.status_code == 200:
                token = response.json()["token"]
                # 测试获取用户信息
                test_get_me(token)
        except:
            pass
    
    # 测试注册
    test_register()
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)
    print("\n如果看到连接错误，请确保:")
    print("1. 后端服务已启动 (python -m uvicorn app.main:app --reload --port 8000)")
    print("2. 已安装必要的依赖 (pip install -r requirements_api.txt)")
    print("3. 服务运行在 http://localhost:8000")

