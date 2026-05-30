import os
import json

# 1. 动态获取当前脚本所在的绝对目录路径
WORK_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. 定义文件的绝对路径
file_a_path = os.path.join(WORK_DIR, "tvbox.json")
file_b_path = os.path.join(WORK_DIR, "tvbox01.json")
output_path = os.path.join(WORK_DIR, "zztvbox.json")

# 初始化最终的汇总容器
zztvbox_data = {}


def load_json(file_path):
    """安全读取 JSON 文件的辅助函数"""
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"读取文件失败 {file_path}: {e}")
    return {}


# 3. 读取两个文件的内容
data_a = load_json(file_a_path)
data_b = load_json(file_b_path)

# 4. 合并所有不重复的顶级键名（获取全部需要处理的分类，如 sites, lives 等）
all_keys = set(data_a.keys()).union(set(data_b.keys()))

for key in all_keys:
    val_a = data_a.get(key)
    val_b = data_b.get(key)

    # 情况 A：两边都是列表（例如 sites: [...], parses: [...]）-> 拼接列表
    if isinstance(val_a, list) and isinstance(val_b, list):
        zztvbox_data[key] = val_a + val_b

    # 情况 B：两边都是字典 -> 合并字典
    elif isinstance(val_a, dict) and isinstance(val_b, dict):
        merged_dict = val_a.copy()
        merged_dict.update(val_b)
        zztvbox_data[key] = merged_dict

    # 情况 C：只有其中一个文件有这个键 -> 直接保留
    elif val_a is not None and val_b is None:
        zztvbox_data[key] = val_a
    elif val_b is not None and val_a is None:
        zztvbox_data[key] = val_b

    # 情况 D：键名相同但类型冲突，或都是普通文本/数字 -> 默认保留后者的值
    else:
        zztvbox_data[key] = val_b if val_b is not None else val_a

# 5. 将真正合并汇总后的内容写入 zztvbox.json
try:
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(zztvbox_data, f, ensure_ascii=False, indent=4)
    print(f"成功！已将 tvbox 和 tvbox01 的内部列表完美合并至: {output_path}")
except Exception as e:
    print(f"写入 zztvbox.json 失败: {e}")
