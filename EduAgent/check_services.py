"""
检查相关服务是否运行
"""
import requests
import socket

def check_port(host, port, timeout=2):
    """检查端口是否开放"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def check_searxng():
    """检查SearxNG服务"""
    print("检查 SearxNG 服务 (localhost:8090)...")
    if check_port('localhost', 8090):
        try:
            r = requests.get('http://localhost:8090/search?q=test&format=json', timeout=3)
            if r.status_code == 200:
                print("  [OK] SearxNG 服务正在运行")
                return True
            else:
                print(f"  [WARNING] SearxNG 端口开放但返回状态码: {r.status_code}")
                return False
        except Exception as e:
            print(f"  [WARNING] SearxNG 端口开放但无法访问: {e}")
            return False
    else:
        print("  [ERROR] SearxNG 服务未运行 (端口8090未开放)")
        print("     提示: 如果SearxNG未运行，web_search会使用Bing/DDG HTML解析，速度较慢")
        return False

def check_fastapi():
    """检查FastAPI服务"""
    print("检查 FastAPI 服务 (localhost:8848)...")
    if check_port('localhost', 8848):
        try:
            r = requests.get('http://localhost:8848/', timeout=3)
            if r.status_code == 200:
                print("  [OK] FastAPI 服务正在运行")
                return True
            else:
                print(f"  [WARNING] FastAPI 端口开放但返回状态码: {r.status_code}")
                return False
        except Exception as e:
            print(f"  [WARNING] FastAPI 端口开放但无法访问: {e}")
            return False
    else:
        print("  [ERROR] FastAPI 服务未运行 (端口8848未开放)")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("服务状态检查")
    print("=" * 60)
    print()
    
    searxng_ok = check_searxng()
    print()
    fastapi_ok = check_fastapi()
    
    print()
    print("=" * 60)
    print("总结")
    print("=" * 60)
    
    if not searxng_ok:
        print("[WARNING] SearxNG未运行 - 这会导致web_search使用较慢的HTML解析方式")
        print("   建议: 启动SearxNG以加快搜索速度")
        print("   命令: docker run -d -p 8090:8080 searxng/searxng")
        print("   或使用: docker-compose -f docker-compose.searxng.yml up -d")
    
    if not fastapi_ok:
        print("[WARNING] FastAPI未运行 - 无法使用API接口")
        print("   建议: 运行 python main.py 启动服务")

