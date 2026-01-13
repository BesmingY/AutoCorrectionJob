from openai import OpenAI
from typing import Optional, List, Dict, Any
import os


class Qwen3LLM:
    """
    使用Qwen3模型的LLM类，通过OpenAI兼容API进行调用
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name: str = "qwen3-235b-a22b"
    ):
        """
        初始化Qwen3 LLM
        
        Args:
            api_key: 阿里云API密钥，如果为None则从环境变量DASHSCOPE_API_KEY获取
            base_url: API基础URL
            model_name: 模型名称
        """
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "请提供API密钥，可以通过参数传递或设置DASHSCOPE_API_KEY环境变量"
            )
            
        self.base_url = base_url
        self.model_name = model_name
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        enable_thinking: bool = False,
        **kwargs
    ) -> str:
        """
        生成文本响应
        
        Args:
            messages: 对话消息列表
            temperature: 温度参数，控制生成的随机性
            max_tokens: 最大生成token数
            enable_thinking: 是否启用思考过程
            **kwargs: 其他参数
            
        Returns:
            模型生成的文本
        """
        try:
            # 构造额外参数
            extra_body = {"enable_thinking": enable_thinking}
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,  # 非流式调用
                extra_body=extra_body,
                **kwargs
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            raise Exception(f"调用Qwen3模型时出错: {str(e)}")
    
    def stream_generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        enable_thinking: bool = False,
        **kwargs
    ):
        """
        流式生成文本响应
        
        Args:
            messages: 对话消息列表
            temperature: 温度参数，控制生成的随机性
            max_tokens: 最大生成token数
            enable_thinking: 是否启用思考过程
            **kwargs: 其他参数
            
        Yields:
            模型生成的文本片段
        """
        try:
            # 构造额外参数
            extra_body = {"enable_thinking": enable_thinking}
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,  # 流式调用
                extra_body=extra_body,
                **kwargs
            )
            
            for chunk in response:
                yield chunk
                
        except Exception as e:
            raise Exception(f"调用Qwen3模型时出错: {str(e)}")


