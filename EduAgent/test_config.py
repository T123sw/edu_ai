"""
测试模型配置是否正确
"""
from o_agent import get_llm_from_config
from langchain_core.messages import HumanMessage

def test_config():
    """测试配置是否正确"""
    print("=" * 60)
    print("测试模型配置")
    print("=" * 60)
    
    try:
        print("\n1. 读取配置文件...")
        import define
        from define import CONFIG_PATH
        import tomllib
        
        with CONFIG_PATH.open('rb') as f:
            config = tomllib.load(f)
        
        # 关键诊断：确认到底导入的是哪个 define.py、读的是哪个 config.toml
        print(f"   define.py 路径: {getattr(define, '__file__', 'unknown')}")
        print(f"   CONFIG_PATH: {CONFIG_PATH}")
        
        print(f"   API Base URL: {config['api_base'].get('remote_model_api_base', '未配置')}")
        print(f"   模型名称: {config['model'].get('llm_model', '未配置')}")
        print(f"   API 密钥: {config['api_key'].get('remote_model_api_key', '')[:15]}...")
        
        # 检查 base_url 是否需要添加 /v1
        base_url = config['api_base'].get('remote_model_api_base', '')
        if base_url and not base_url.endswith('/v1'):
            print(f"\n   ⚠️  提示: base_url 可能需要添加 /v1 后缀")
            print(f"   当前: {base_url}")
            print(f"   建议: {base_url}/v1")
        
        llm = get_llm_from_config()
        print("   ✅ 配置读取成功")
        
        print("\n2. 测试模型调用...")
        response = llm.invoke([
            HumanMessage(content="你好，请简单回复'配置成功'，不要多说其他内容")
        ])
        print(f"   ✅ 模型调用成功")
        print(f"   模型响应: {response.content}")
        
        print("\n" + "=" * 60)
        print("✅ 配置测试通过！")
        print("=" * 60)
        return True
        
    except ValueError as e:
        print(f"\n❌ 配置错误: {e}")
        print("\n请检查 config.toml 文件：")
        print("  1. 确保配置了 API 密钥（deepseek_api_key 或 remote_model_api_key）")
        print("  2. 检查配置文件格式是否正确")
        return False
        
    except Exception as e:
        print(f"\n❌ 测试失败: {type(e).__name__}: {e}")
        print("\n可能的原因：")
        print("  1. API 密钥无效")
        print("  2. API 服务不可访问")
        print("  3. 模型名称不正确")
        print("  4. 网络连接问题")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_config()

