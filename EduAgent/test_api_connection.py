"""
测试 API 连接和配置
"""
import requests
from o_agent import get_llm_from_config
from langchain_core.messages import HumanMessage

def test_api_endpoint():
    """测试 API 端点是否可访问"""
    print("=" * 60)
    print("测试 API 端点连接")
    print("=" * 60)
    
    base_url = "https://1lmapi.blsc.cn"
    
    # 测试 1: 检查基础端点
    print(f"\n1. 测试基础端点: {base_url}")
    try:
        response = requests.get(f"{base_url}/v1/models", timeout=10)
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ 端点可访问")
            print(f"   响应: {response.text[:200]}")
        else:
            print(f"   ⚠️  端点返回: {response.status_code}")
            print(f"   响应: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
    
    # 测试 2: 检查不同的路径
    paths = ["/v1/models", "/models", "/api/v1/models", "/"]
    for path in paths:
        try:
            url = f"{base_url}{path}"
            print(f"\n2. 测试路径: {url}")
            response = requests.get(url, timeout=5)
            print(f"   状态码: {response.status_code}")
            if response.status_code == 200:
                print(f"   ✅ 路径可访问")
        except Exception as e:
            print(f"   ❌ 路径不可访问: {type(e).__name__}")

def test_config_details():
    """显示配置详情"""
    print("\n" + "=" * 60)
    print("当前配置详情")
    print("=" * 60)
    
    try:
        from define import CONFIG_PATH
        import tomllib
        
        with CONFIG_PATH.open('rb') as f:
            config = tomllib.load(f)
        
        print(f"\nAPI 密钥: {config['api_key'].get('remote_model_api_key', '')[:10]}...")
        print(f"模型供应商: {config['model'].get('llm_supply', '')}")
        print(f"模型名称: {config['model'].get('llm_model', '')}")
        print(f"API Base URL: {config['api_base'].get('remote_model_api_base', '')}")
        
    except Exception as e:
        print(f"❌ 读取配置失败: {e}")

def test_with_different_base_urls():
    """尝试不同的 base_url 格式"""
    print("\n" + "=" * 60)
    print("测试不同的 base_url 格式")
    print("=" * 60)
    
    base_urls = [
        "https://1lmapi.blsc.cn",
        "https://1lmapi.blsc.cn/v1",
        "https://1lmapi.blsc.cn/api/v1",
    ]
    
    for base_url in base_urls:
        print(f"\n测试 base_url: {base_url}")
        try:
            from define import CONFIG_PATH
            import tomllib
            from o_agent.llm.llms import get_llm_by_type
            
            with CONFIG_PATH.open('rb') as f:
                config = tomllib.load(f)
            
            api_key = config['api_key'].get('remote_model_api_key', '')
            model = config['model'].get('llm_model', 'deepseek-chat')
            
            llm = get_llm_by_type(
                supply='deepseek',
                model=model,
                api_key=api_key,
                temperature=0.2,
                base_url=base_url
            )
            
            response = llm.invoke([HumanMessage(content="你好")])
            print(f"   ✅ 成功！响应: {response.content[:50]}")
            return True
            
        except Exception as e:
            print(f"   ❌ 失败: {type(e).__name__}: {str(e)[:100]}")
    
    return False

if __name__ == "__main__":
    test_config_details()
    test_api_endpoint()
    test_with_different_base_urls()

