import json
import os
from datetime import datetime

# 获取当前时间（格式：年-月-日 时:分:秒）
current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 定义数据结构
data = {"last_updated": current_time}

# 获取当前脚本所在目录，确保在同级路径下创建
current_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(current_dir, "01.json")

# 写入 JSON 文件
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print(f"成功更新 01.json，当前时间: {current_time}")
