import os
import json

# 1. 动态获取当前脚本所在的绝对目录路径
WORK_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. 定义文件的绝对路径
file_a_path = os.path.join(WORK_DIR, "tvbox01.json")
file_b_path = os.path.join(WORK_DIR, "tvbox.json")
output_path = os.path.join(WORK_DIR, "zztvbox.json")

# 初始化一个空的字典，用于存放合并后的汇总数据
merged_data = {}

# 3. 读取第一个文件 tvbox.json
if os.path.exists(file_a_path):
    try:
        with open(file_a_path, "r", encoding="utf-8") as f:
            data_a = json.load(f)
            if isinstance(data_a, dict):
                merged_data.update(data_a)
            else:
                print("警告: tvbox.json 的根节点不是字典对象，无法直接 update。")
    except Exception as e:
        print(f"读取 tvbox.json 失败: {e}")
else:
    print("未找到 tvbox.json，跳过此文件。")

# 4. 读取第二个文件 tvbox01.json 并汇总
if os.path.exists(file_b_path):
    try:
        with open(file_b_path, "r", encoding="utf-8") as f:
            data_b = json.load(f)
            if isinstance(data_b, dict):
                # update 会合并两个字典。如果键名（Key）重复，后者会覆盖前者
                merged_data.update(data_b)
            else:
                print("警告: tvbox01.json 的根节点不是字典对象，无法直接 update。")
    except Exception as e:
        print(f"读取 tvbox01.json 失败: {e}")
else:
    print("未找到 tvbox01.json，跳过此文件。")

# 5. 将汇总后的内容写入新的 zztvbox.json
try:
    with open(output_path, "w", encoding="utf-8") as f:
        # ensure_ascii=False 确保中文不会变成 \uXXXX 这种乱码
        # indent=4 让输出的 JSON 文本自带缩进，方便人类阅读
        json.dump(merged_data, f, ensure_ascii=False, indent=4)
    print(f"成功！合并后的数据已写入: {output_path}")
except Exception as e:
    print(f"写入 zztvbox.json 失败: {e}")
