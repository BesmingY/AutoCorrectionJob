#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

def get_cpp_content(file_path):
    """
    读取.cpp或.h文件并返回其中的代码内容
    
    Args:
        file_path (str): .cpp或.h文件的路径
    
    Returns:
        str: 文件中的代码内容
    """
    if not (file_path.endswith('.cpp') or file_path.endswith('.h')):
        print("警告: 输入的文件可能不是C++文件或头文件")
    
    # 尝试多种编码方式读取文件
    encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                content = file.read()
            print(f"成功使用 {encoding} 编码读取文件 {file_path}")
            return content
        except UnicodeDecodeError:
            print(f"使用 {encoding} 编码读取文件失败")
            continue
        except FileNotFoundError:
            print(f"错误: 找不到文件 '{file_path}'")
            return None
        except Exception as e:
            print(f"读取文件时出错: {e}")
            continue
    
    print(f"错误: 无法使用任何支持的编码读取文件 '{file_path}'")
    return None

def main():
    if len(sys.argv) != 2:
        print("使用方法: python get_content.py <cpp_file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    # 检查文件扩展名
    if not file_path.endswith('.cpp'):
        print("警告: 输入的文件可能不是C++文件")
    
    content = get_cpp_content(file_path)
    
    if content is not None:
        print(content)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()