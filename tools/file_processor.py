from typing import Optional, List, Dict, Any
import re


def extract_student_info(filename):
    """
    从文件名中提取学号和姓名
    假设文件名格式为: 学号姓名（其他信息）.zip 或类似格式
    """
    # 移除.zip扩展名
    name_without_ext = filename.replace(".zip", "")
    
    # 使用正则表达式匹配学号(数字)和姓名(中文)
    # 假设学号是连续的数字，姓名是连续的中文字符
    student_id_match = re.search(r'\d+', name_without_ext)
    student_name_match = re.search(r'[\u4e00-\u9fa5]+', name_without_ext)
    
    student_id = student_id_match.group() if student_id_match else ""
    student_name = student_name_match.group() if student_name_match else name_without_ext
    
    return student_id, student_name



