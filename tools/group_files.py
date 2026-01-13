from typing import Optional, List, Dict, Any
import os
import re
import json
from tools.llm import Qwen3LLM

def group_files_by_question(contents: Dict[str, str],requirements) -> Dict[str, str]:
    """
    使用LLM对文件进行分组，将属于同一题目的CPP文件内容合并
    
    Args:
        contents: 文件路径到内容的映射
        
    Returns:
        分组后的文件内容，键为组标识，值为合并后的内容
    """
    if not contents:
        return {}
    print(f"正在合并文件，请稍等...")
    # 构建文件列表描述
    file_descriptions = []
    for file_path, content in contents.items():
        # 提取文件名
        file_name = os.path.basename(file_path)
        file_descriptions.append(f"文件路径: {file_path}文件名: {file_name}\n内容预览: {content[:200]}...\n")
    
    # 创建LLM提示
    prompt = f"""
作为一名专业的C++编程老师，请仔细分析以下残缺的C++作业文件。

文件列表:
{chr(10).join(file_descriptions)}
/n
这是本次作业要求："/n{requirements}/n"
前面提到的文件列表实际上都是关于上述作业要求的作答文件，
1.先根据文件路径看一下是否有明显题目归类，比如几个文件来自同一文件夹，他们很可能是属于同一类题。
2.再根据文件内容和作业要求进一步确认，将不同的作业文件进行归类到对应题目。
只需返回文件名。/n

请按照以下格式返回分组结果：
[<question>题目序号</question>, <files>[文件名1, 文件名2, ...]</files>]
每题一行，例如：
[<question>q1</question>, <files>[files1_part1.cpp, files1_part2.cpp]</files>]
[<question>q2</question>, <files>[files2.cpp]</files>]

注意事项：
1. 如果一个文件独立属于一个题目，则单独成组
2. 如果多个文件属于同一题目（如题目的不同部分、版本或实现），请将它们分在同一题目下
3. 也可能一个文件属于多个组（比如题目间有依赖关系）
4. 题目标识为q1, q2等
5. 每个文件可能被多个main函数调用，也就是属于不同组，这一点要仔细分辨
6. 如果有题目没有对应的作答文件，你要返回对应题号，和空列表，如[<question>q5</question>, <files></files>]
7. 还有一个重难点！！！！！
有些题目有依赖关系，比如题目2是题目1的扩展，题目3是题目2的扩展
你要分辨清楚这些依赖关系，题目依然要分组，但是题目1的组的文件也要加入题目2中，题目2的组的文件也要加入题目3中
也就是题目2的组的文件 = 题目1的组的文件 + 题目2的组的文件
"""
    
    llm = Qwen3LLM()
    messages = [
        {"role": "system", "content": "你是一个专业的C++编程老师，善于分析学生提交的作业文件结构。"},
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = llm.generate(messages, temperature=0.1)
        print(f"LLM文件分组结果: {response}")
        
        # 解析LLM响应
        grouped_files = parse_grouping_response(response, contents)
        return grouped_files
        
    except Exception as e:
        print(f"LLM分组失败: {e}")
        # 如果LLM分组失败，则每个文件独立成组
        return create_default_groups(contents)


def parse_grouping_response(response: str, contents: Dict[str, str]) -> Dict[str, str]:
    """
    解析LLM的分组响应
    """
    grouped_contents = {}
    
    # 改进的正则表达式
    pattern = r'\[<question>([^<]+)</question>\s*,\s*<files>(.*?)</files>\]'
    
    matches = re.findall(pattern, response, re.DOTALL)
    
    if not matches:
        print("未找到有效的分组格式，返回空分组")
        return grouped_contents  # 返回空字典，即丢弃所有文件
    
    # 创建文件名到路径的映射
    filename_to_path = {os.path.basename(path): path for path in contents.keys()}
    
    for group_name, files_str in matches:
        # 清理文件名字符串
        files_str = files_str.strip()
        files_str = files_str.strip('[]')  # 移除可能的方括号
        
        # 多种分隔符处理
        file_names = []
        if ',' in files_str:
            file_names = [f.strip().strip('"\'') for f in files_str.split(',')]
        else:
            file_names = [files_str.strip().strip('"\'')]
        
        # 过滤空文件名
        file_names = [f for f in file_names if f]
        
        if not file_names:
            continue
            
        print(f"题目 '{group_name}': {file_names}")
        
        # 合并同一组的文件内容
        merged_content = ""
        found_files = 0
        for file_name in file_names:
            if file_name in filename_to_path:
                file_path = filename_to_path[file_name]
                content = contents[file_path]
                merged_content += f"//=== {file_name} ===\n{content}\n\n"
                found_files += 1
            else:
                print(f"警告: 文件 '{file_name}' 在提取的文件中不存在")
        
        if merged_content and found_files > 0:
            grouped_contents[group_name] = merged_content
            print(f"分组 '{group_name}' 成功合并 {found_files} 个文件")
        else:
            print(f"警告: 分组 '{group_name}' 没有找到有效文件")
    
    # 不再处理未被分组的文件，直接丢弃
    return grouped_contents


def create_default_groups(contents: Dict[str, str]) -> Dict[str, str]:
    """
    当LLM分组失败时创建默认分组（每个文件独立成组）
    
    Args:
        contents: 文件内容映射
        
    Returns:
        默认分组的内容
    """
    grouped_contents = {}
    for i, (file_path, content) in enumerate(contents.items()):
        file_name = os.path.basename(file_path)
        group_name = f"files{i+1}"
        grouped_contents[group_name] = f"//=== {file_name} ===\n{content}\n"
    
    return grouped_contents