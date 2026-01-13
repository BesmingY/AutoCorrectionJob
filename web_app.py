from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
import os
import sys
import re
from werkzeug.utils import secure_filename
import threading
import time
import json

# 导入项目相关模块
sys.path.append('.')

from main import save_results_to_csv
from preprocessor.merge_zip import main_processor as merge_zips
from template.simpleTemplate import SCORE_ONE, SUMMARY_SCORE, ABC_ONE, SUMMARY_ABC

# 从tools模块导入所有必要组件
from tools.llm import Qwen3LLM
from tools.get_files import extract_and_list_files
from tools.get_content import get_cpp_content
from tools.group_files import group_files_by_question
from tools.file_processor import extract_student_info

app = Flask(__name__)

# 配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'zip'}
PROCESSED_ZIPS_DIR = 'collected_zips'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_homework_workflow(search_dir, requirements, num_questions, assignment_type, base_url, model_name, api_key):
    """
    处理作业的完整流程：合并ZIP文件，然后批改
    
    Args:
        search_dir: 包含学生作业ZIP文件的目录
        requirements: 作业要求
        num_questions: 题目数量
        assignment_type: 作业类型
        base_url: LLM API基础URL
        model_name: 模型名称
        api_key: API密钥
        
    Yields:
        JSON格式的进度更新信息
    """
    import os
    import csv
    import zipfile
    import shutil
    import sys
    from collections import Counter
    
    # 强制 stdout 使用 UTF-8
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
    # 确定临时输出目录
    temp_output_dir = PROCESSED_ZIPS_DIR
    
    yield json.dumps({
        "type": "info",
        "message": f"开始合并ZIP文件，搜索目录: {search_dir}"
    }, ensure_ascii=False) + "\n"
    
    # 合并ZIP文件
    from preprocessor.merge_zip import find_all_zip_files, copy_and_ensure_valid
    
    zip_files = find_all_zip_files(search_dir)
    
    yield json.dumps({
        "type": "info",
        "message": f"在 {search_dir} 中找到 {len(zip_files)} 个ZIP文件"
    }, ensure_ascii=False) + "\n"
    
    # 确保输出目录存在
    os.makedirs(temp_output_dir, exist_ok=True)
    
    success, failed = copy_and_ensure_valid(zip_files, temp_output_dir)
    
    yield json.dumps({
        "type": "info",
        "message": f"ZIP文件合并完成，成功处理 {success} 个文件"
    }, ensure_ascii=False) + "\n"
    
    if failed:
        yield json.dumps({
            "type": "warning",
            "message": f"有 {len(failed)} 个文件处理失败"
        }, ensure_ascii=False) + "\n"

    # 根据作业类型选择模板
    if assignment_type == "实验":
        templates = {
            "single": SCORE_ONE,
            "summary": SUMMARY_SCORE
        }
    elif assignment_type == "理论":
        templates = {
            "single": ABC_ONE,
            "summary": SUMMARY_ABC
        }
    else:
        yield json.dumps({
            "type": "error",
            "message": f"未知的作业类型: {assignment_type}"
        }, ensure_ascii=False) + "\n"
        return

    # 批量处理作业
    results = []
    
    # 获取目录下所有的zip文件
    zip_files = [f for f in os.listdir(temp_output_dir) if f.endswith('.zip')]
    
    yield json.dumps({
        "type": "info",
        "message": f"开始批改作业，共有 {len(zip_files)} 份作业"
    }, ensure_ascii=False) + "\n"
    
    for i, zip_file in enumerate(zip_files):
        yield json.dumps({
            "type": "info", 
            "message": f"正在处理第 {i+1}/{len(zip_files)} 份作业: {zip_file}"
        }, ensure_ascii=False) + "\n"
        
        # 提取学号和姓名
        student_id, student_name = extract_student_info(zip_file)
        yield json.dumps({
            "type": "info",
            "message": f"学号: {student_id}, 姓名: {student_name}"
        }, ensure_ascii=False) + "\n"
        
        zip_path = os.path.join(temp_output_dir, zip_file)
        
        # 检查是否是有效的zip文件
        if not zipfile.is_zipfile(zip_path):
            yield json.dumps({
                "type": "warning",
                "message": f"警告: {zip_file} 不是一个有效的ZIP文件，跳过处理"
            }, ensure_ascii=False) + "\n"
            results.append({
                "student_id": student_id,
                "student_name": student_name,
                "score": -1,
                "feedback": "无效的ZIP文件"
            })
            continue
            
        # 获取文件内容
        try:
            files = extract_and_list_files(zip_path, extract_to="temp")
            yield json.dumps({
                "type": "info",
                "message": f"已提取 {len(files)} 个文件"
            }, ensure_ascii=False) + "\n"
        except Exception as e:
            try:
                error_msg = str(e)
            except UnicodeError:
                error_msg = repr(e)
            
            if isinstance(error_msg, str):
                try:
                    error_msg.encode(sys.stdout.encoding or 'utf-8', errors='replace')
                except Exception:
                    error_msg = error_msg.encode('utf-8', errors='replace').decode('utf-8')
            
            yield json.dumps({
                "type": "error",
                "message": f"提取文件失败: {error_msg}"
            }, ensure_ascii=False) + "\n"
            results.append({
                "student_id": student_id,
                "student_name": student_name,
                "score": -1,
                "feedback": f"提取文件失败: {error_msg}"
            })
            continue
        
        contents = {}
        for file_path in files:
            if file_path.endswith('.cpp') or file_path.endswith('.h'):
                content = get_cpp_content(file_path)
                if content:
                    # 使用文件路径作为键，而不是仅文件名
                    contents[file_path] = content
                else:
                    yield json.dumps({
                        "type": "warning",
                        "message": f"读取文件内容失败: {file_path}"
                    }, ensure_ascii=False) + "\n"
        
        # 调用LLM对文件进行分组，识别属于同一题目的文件
        contents = group_files_by_question(contents, requirements)
        
        # 删除temp文件夹
        shutil.rmtree("temp", ignore_errors=True)
        
        # 初始化自定义LLM
        llm = Qwen3LLM(api_key=api_key, base_url=base_url, model_name=model_name)
        
        # 开始评分
        contents_list = []
        scores = []
        score_summary = ""
        for key, value in contents.items():
            contents_list.append(f"文件名: {key}\n代码内容:\n{value}\n==================\n")
            result = grad_one_with_custom_llm(value, requirements, templates["single"], llm)
            scores.append(result)
            score_summary += f"文件: {key} 得分: {result['score']}\n"
        
        cpp_code = "\n".join(contents_list)
        
        if assignment_type == "实验":
            sum_score = 0
            if len(scores) < num_questions:
                yield json.dumps({
                    "type": "warning",
                    "message": "作业数量与题目数量不一致"
                }, ensure_ascii=False) + "\n"
                score_final = -2
            else:
                for ans in scores:
                    score = int(ans["score"])
                    if score >= 0:
                        sum_score += score
                if len(scores) == 0:
                    yield json.dumps({
                        "type": "warning",
                        "message": "作业总数除0"
                    }, ensure_ascii=False) + "\n"
                score_final = sum_score // len(scores) if len(scores) > 0 else 0
        elif assignment_type == "理论":
            if len(scores) < num_questions:
                if len(scores) > 3:
                    score_final = "C"
                else:
                    yield json.dumps({
                        "type": "warning",
                        "message": "作业数量与题目数量不一致"
                    }, ensure_ascii=False) + "\n"
                    score_final = -2
            else:
                score_values = [score_dict["score"] for score_dict in scores if "score" in score_dict]
                score_final = Counter(score_values).most_common(1)[0][0] if score_values else "D"

        # 生成总结
        prompt = templates["summary"].format(
            requirements=requirements,
            cpp_code=cpp_code,
            score_summary=score_summary
        )

        messages = [
            {"role": "system", "content": "你是一个专业的C++编程老师，善于批改学生作业。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            # 使用流式调用并处理思考过程
            response = llm.generate(messages, temperature=0.1, enable_thinking=False)

            # 处理响应内容
            if response:
                llm_response = response
                yield json.dumps({
                    "type": "info",
                    "message": f"总结：{llm_response[:100]}..."  # 只显示前100个字符
                }, ensure_ascii=False) + "\n"
            else:
                llm_response = "LLM未生成任何响应内容"

        except Exception as e:
            llm_response = f"LLM反馈生成失败: {str(e)}"
            yield json.dumps({
                "type": "error",
                "message": llm_response
            }, ensure_ascii=False) + "\n"

        results.append({
            "student_id": student_id,
            "student_name": student_name,
            "score": score_final,
            "feedback": llm_response
        })
        yield json.dumps({
            "type": "info",
            "message": f"处理完成: {student_name} - 得分: {score_final}"
        }, ensure_ascii=False) + "\n"
    
    # 保存结果
    output_file = f"grading_results_{int(time.time())}.csv"
    save_results_to_csv(results, output_file=output_file)
    
    # 清理收集的zip文件
    try:
        shutil.rmtree(temp_output_dir)
        yield json.dumps({
            "type": "info",
            "message": f"已清理临时文件目录: {temp_output_dir}"
        }, ensure_ascii=False) + "\n"
    except Exception as e:
        yield json.dumps({
            "type": "warning",
            "message": f"清理临时文件目录失败: {str(e)}"
        }, ensure_ascii=False) + "\n"
    
    yield json.dumps({
        "type": "success",
        "message": f"批改完成！共处理 {len(results)} 份作业，结果已保存至 {output_file}",
        "results_count": len(results),
        "output_file": output_file
    }, ensure_ascii=False) + "\n"


def grad_one_with_custom_llm(content, requirements, template, llm):
    prompt = template.format(requirements=requirements, content=content)
    
    messages = [
        {"role": "system", "content": "你是一个专业的C++编程老师，善于批改学生作业。"},
        {"role": "user", "content": prompt}
    ]
    
    try:
        # 使用流式调用并处理思考过程
        response = llm.generate(messages, temperature=0.1, enable_thinking=False)
        
        if not response:
            return {"question": -1, "score": -1}
            
        # 直接从响应中提取题号和分数
        llm_response = response.strip()
        print(f"LLM题目评分: {llm_response}")
        
        # 使用正则表达式匹配标准格式 [<question>题号</question>,<score>分数</score>]
        pattern = r'\[<question>(-?\d+)</question>\s*,\s*<score>([A-Za-z0-9]+)</score>\]'
        match = re.search(pattern, llm_response)
        
        if match:
            question = match.group(1)
            score = match.group(2)
            return {"question": question, "score": score}
        else:
            # 如果标准格式匹配失败，尝试更宽松的匹配方式
            print("标准格式匹配失败，尝试宽松匹配...")
            
            # 尝试匹配题号
            question_match = re.search(r'<question>(-?\d+)</question>', llm_response)
            if not question_match:
                # 尝试其他可能的题号表示方式
                question_match = re.search(r'题号[：:]?\s*(-?\d+)', llm_response)
            
            # 尝试匹配分数
            score_match = re.search(r'<score>(-?\d+)</score>', llm_response)
            if not score_match:
                # 尝试其他可能的分数表示方式
                score_match = re.search(r'分数[：:]?\s*(-?\d+)', llm_response)
            
            if question_match and score_match:
                question = int(question_match.group(1))
                score = int(score_match.group(1))
                return {"question": question, "score": score}
            else:
                # 如果所有匹配都失败，返回默认值
                print("无法从响应中提取题号和分数")
                return {"question": -1, "score": -1}
                
    except Exception as e:
        print(f"LLM调用或解析失败: {str(e)}")
        return {"question": -99, "score": -99}

def save_results_to_csv(results, output_file="grading_results.csv"):
    """
    将评分结果保存为CSV文件
    
    Args:
        results: 评分结果列表
        output_file: 输出文件名
    """
    import csv
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ['学号', '姓名', '得分', '作业情况']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for result in results:
            writer.writerow({
                '学号': result['student_id'],
                '姓名': result['student_name'],
                '得分': result['score'],
                '作业情况': result['feedback']
            })
    
    print(f"评分结果已保存至 {output_file}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_homework():
    try:
        # 获取表单数据并清理可能存在的引号
        search_dir = request.form.get('searchDir', '').strip().strip('"\'')
        assignment_type = request.form.get('assignment_type', '').strip()
        requirements = request.form.get('requirements', '').strip()
        num_questions_str = request.form.get('num_questions', '1').strip()
        base_url = request.form.get('base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1').strip()
        model_name = request.form.get('model_name', 'qwen3-235b-a22b').strip()
        api_key = request.form.get('api_key', '').strip()
        
        # 验证必要参数
        if not search_dir:
            return jsonify({"error": "缺少搜索目录路径"}), 400
        if not requirements:
            return jsonify({"error": "缺少作业要求"}), 400
        if not api_key:
            return jsonify({"error": "缺少API密钥"}), 400
            
        # 转制题目数量为整数
        try:
            num_questions = int(num_questions_str)
        except ValueError:
            return jsonify({"error": "题目数量必须是数字"}), 400
        
        # 验证路径是否存在
        if not os.path.isdir(search_dir):
            return jsonify({"error": f"搜索目录不存在: {search_dir}"}), 400
        
        # 返回流式响应
        def generate():
            for chunk in process_homework_workflow(
                search_dir=search_dir,
                requirements=requirements,
                num_questions=num_questions,
                assignment_type=assignment_type,
                base_url=base_url,
                model_name=model_name,
                api_key=api_key
            ):
                yield chunk
        
        return Response(generate(), mimetype='application/json; charset=utf-8')
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # 创建必要的目录
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(PROCESSED_ZIPS_DIR, exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)