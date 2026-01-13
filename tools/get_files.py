import sys
import os
import zipfile
import tempfile
import argparse

def extract_and_list_files(zip_path, extract_to=None, cleanup=True):
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"ZIP 文件不存在: {zip_path}")

    if extract_to is None:
        temp_dir = tempfile.mkdtemp()
        extract_to = temp_dir
    else:
        os.makedirs(extract_to, exist_ok=True)
        temp_dir = None

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file in zip_ref.namelist():
                try:
                    # 尝试多种编码方式处理中文文件名
                    file_name = file.encode('cp437').decode('gbk')
                except:
                    try:
                        file_name = file.encode('utf-8').decode('utf-8')
                    except:
                        file_name = file  # 如果都失败，使用原始文件名
                
                dst_path = os.path.join(extract_to, file_name)
                
                if os.path.exists(dst_path):
                    os.remove(dst_path)
                
                zip_ref.extract(file, extract_to)
                
                src_path = os.path.join(extract_to, file)
                if os.path.exists(src_path) and src_path != dst_path:
                    os.rename(src_path, dst_path)

        file_paths = []
        for root, dirs, files in os.walk(extract_to):
            for file in files:
                full_path = os.path.join(root, file)
                file_paths.append(os.path.abspath(full_path))

        return file_paths

    finally:
        if cleanup and temp_dir and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)

def main():
    parser = argparse.ArgumentParser(description="解压 ZIP 文件并列出所有普通文件（非文件夹）")
    parser.add_argument("zip_file", help="输入的 ZIP 文件路径")
    parser.add_argument("-o", "--output-dir", help="可选：指定解压目录（默认使用临时目录）")
    parser.add_argument("--no-cleanup", action="store_true", help="不解压后不删除临时目录")

    args = parser.parse_args()

    try:
        files = extract_and_list_files(
            zip_path=args.zip_file,
            extract_to=args.output_dir,
            cleanup=not args.no_cleanup
        )
        print(f"共找到 {len(files)} 个文件：")
        for f in files:
            print(f)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()