from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from typing import Optional
from pathlib import Path
import tomllib


LLM_MAP = {
    'deepseek': ChatDeepSeek,
    'openai': ChatOpenAI
}


def get_llm_by_type(
    supply: str, 
    model: str, 
    temperature: float, 
    api_key: str,
    max_tokens: int = 7000,
    base_url: Optional[str] = None,
    timeout: Optional[float] = 60.0,
    max_retries: Optional[int] = 2,
):
    """
    获取 LLM 实例
    
    :param supply: 供应商类型 ('deepseek' 或 'openai')
    :param model: 模型名称
    :param temperature: 温度参数 (0.0-2.0)
    :param api_key: API 密钥
    :param max_tokens: 最大输出长度
    :param base_url: 自定义 API 基础地址（可选）
    :return: 可调用的模型实例
    """
    llm_class = LLM_MAP[supply]
    
    # 构建参数
    params = {
        'model': model,
        'temperature': temperature,
        'max_tokens': max_tokens,
        'api_key': api_key
    }

    # 为不同 LangChain LLM 适配超时/重试参数（不同版本字段名可能不同）
    if timeout is not None:
        # langchain-openai / openai-python 常见字段：timeout / request_timeout
        params['timeout'] = timeout
        params['request_timeout'] = timeout
    if max_retries is not None:
        params['max_retries'] = max_retries
    
    # 如果提供了 base_url，做一次兼容性归一化：
    # - 许多 OpenAI 兼容服务要求 base_url 以 /v1 结尾
    # - 你给的配置可能是根域名（如 https://llmapi.blsc.cn）
    if base_url:
        base = base_url.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        params['base_url'] = base
    
    # 有些类不接受 request_timeout/max_retries 等参数，做一次兼容性回退
    try:
        return llm_class(**params)
    except TypeError:
        for k in ('request_timeout', 'max_retries', 'timeout'):
            params.pop(k, None)
        return llm_class(**params)


def get_llm_from_config(
    config_path: Optional[Path] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
):
    """
    从配置文件获取 LLM 实例（便捷函数）
    
    :param config_path: 配置文件路径，默认使用 define.py 中的 CONFIG_PATH
    :param temperature: 温度参数，如果为 None 则使用配置文件中的值
    :param max_tokens: 最大 token 数，如果为 None 则使用配置文件中的值
    :return: LLM 实例
    """
    if config_path is None:
        from define import CONFIG_PATH
        config_path = CONFIG_PATH
    
    with config_path.open('rb') as f:
        config = tomllib.load(f)
    
    # 获取 API 密钥（优先使用 remote_model_api_key）
    api_key = config['api_key'].get('remote_model_api_key') or config['api_key'].get('deepseek_api_key', '')
    if not api_key:
        raise ValueError("未配置 API 密钥，请在 config.toml 中设置 deepseek_api_key 或 remote_model_api_key")
    
    # 获取模型配置
    model_config = config.get('model', {})
    llm_supply = model_config.get('llm_supply', 'deepseek')
    llm_model = model_config.get('llm_model', 'deepseek-chat')
    temp = temperature if temperature is not None else model_config.get('temperature', 0.2)
    max_tok = max_tokens if max_tokens is not None else model_config.get('max_tokens', 7000)
    req_timeout = timeout if timeout is not None else model_config.get('timeout', 60.0)
    retries = max_retries if max_retries is not None else model_config.get('max_retries', 2)
    
    # 获取 API base URL
    api_base_config = config.get('api_base', {})
    base_url = api_base_config.get('remote_model_api_base') or None
    
    return get_llm_by_type(
        supply=llm_supply,
        model=llm_model,
        api_key=api_key,
        temperature=temp,
        max_tokens=max_tok,
        base_url=base_url,
        timeout=req_timeout,
        max_retries=retries,
    )
