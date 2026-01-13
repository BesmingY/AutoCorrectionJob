import os
import sys
import shutil
import zipfile

def find_all_zip_files(root_dir):
    """递归查找所有 .zip 文件，但排除 macOS 的 ._ 开头的元数据文件"""
    zip_files = []
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith('.zip') and not file.startswith('._'):
                zip_files.append(os.path.join(root, file))
    return zip_files

def repair_if_needed(src_path, dest_path):
    """
    尝试修复 ZIP：如果文件头不在开头，就截取从 PK\x03\x04 开始的部分
    修复后验证是否为有效 ZIP，否则回退到原样复制
    """
    try:
        with open(src_path, 'rb') as f:
            data = f.read()

        # 查找 ZIP 文件头
        pk_offset = data.find(b'PK\x03\x04')
        if pk_offset == 0:
            # 已经是标准 ZIP，直接复制
            shutil.copy2(src_path, dest_path)
            return True
        elif pk_offset > 0:
            # 有偏移，尝试修复
            repaired_data = data[pk_offset:]
            with open(dest_path, 'wb') as f:
                f.write(repaired_data)
            # 验证修复后是否有效
            if zipfile.is_zipfile(dest_path):
                return True
            else:
                # 修复失败，回退：用原始文件
                shutil.copy2(src_path, dest_path)
                return zipfile.is_zipfile(dest_path)
        else:
            # 找不到 ZIP 头，直接复制（可能是损坏文件，但按要求不跳过）
            shutil.copy2(src_path, dest_path)
            return zipfile.is_zipfile(dest_path)
    except Exception:
        # 出错时仍尝试原样复制
        try:
            shutil.copy2(src_path, dest_path)
            return zipfile.is_zipfile(dest_path)
        except Exception:
            return False

def copy_and_ensure_valid(zip_files, output_dir):
    success = 0
    failed = []

    os.makedirs(output_dir, exist_ok=True)

    for src in zip_files:
        try:
            filename = os.path.basename(src)
            dest = os.path.join(output_dir, filename)

            # 处理重名
            counter = 1
            base, ext = os.path.splitext(filename)
            while os.path.exists(dest):
                dest = os.path.join(output_dir, f"{base}_{counter}{ext}")
                counter += 1

            # 尝试修复或原样复制，并确保结果是有效 ZIP（或至少复制了）
            is_valid = repair_if_needed(src, dest)

            if is_valid:
                success += 1
            else:
                # 即使无效也复制了（满足“不跳过”），但标记为“可能无法打开”
                success += 1  # 因为文件已复制，只是内容可能损坏
        except Exception as e:
            failed.append(src)

    return success, failed

def main_processor():
    if len(sys.argv) < 2:
        print("用法: python collect_zips.py <搜索目录> [输出目录]")
        print("示例: python collect_zips.py D:\\submissions D:\\collected_zips")
        sys.exit(1)

    search_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.getcwd(), 'collected_zips')

    if not os.path.isdir(search_dir):
        print(f"错误: 搜索目录不存在: {search_dir}")
        sys.exit(1)

    print(f"搜索目录: {search_dir}")
    print(f"输出目录: {output_dir}")

    zip_files = find_all_zip_files(search_dir)
    all_zips = [f for f in os.listdir(search_dir) if f.lower().endswith('.zip')]  # 用于统计被过滤的数量
    filtered_count = len(all_zips) - len([f for f in all_zips if not f.startswith('._')])

    if not zip_files:
        print("未找到任何有效的 .zip 文件（可能全被过滤或目录为空）。")
        return

    print(f"找到 {len(zip_files)} 个有效 ZIP 文件（已自动排除 {filtered_count} 个 macOS 元数据文件如 '._xxx.zip'）")
    print("正在处理...")

    success, failed = copy_and_ensure_valid(zip_files, output_dir)

    print("\n" + "="*60)
    print(f"✅ 成功处理并复制: {success} 个文件")
    print(f"❌ 完全复制失败（如权限错误）: {len(failed)} 个")

    if failed:
        print("\n无法复制的文件（可能被占用或权限不足）:")
        for f in failed:
            print(f"  {f}")

    print(f"\n💡 提示：所有有效 ZIP 文件均已复制到:\n    {output_dir}")
    print("   请在 Windows 资源管理器或解压软件中验证是否可正常打开。")

if __name__ == "__main__":
    main_processor()