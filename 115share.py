#!/usr/bin/env python3
# encoding: utf-8

__author__ = "wishilb0 <https://github.com/wishilb0>"

import os
import re
import json
import sqlite3
from pathlib import Path
from p115 import P115Client, P115FileSystem

# 读取 cookies
cookies_path = Path("115-cookies.txt")
cookies = cookies_path.read_text(encoding="utf-8").strip()

# 初始化 115 客户端
client = P115Client(cookies=cookies)

# 加载映射关系
with open("txt_cid_map.json", "r", encoding="utf-8") as f:
    txt_to_cid_map = json.load(f)

# 初始化数据库
db_path = '115shared_links.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute(''' 
    CREATE TABLE IF NOT EXISTS received_shares ( 
        share_code TEXT PRIMARY KEY, 
        receive_code TEXT, 
        txt_file TEXT, 
        cid INTEGER, 
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP 
    ) 
''')
conn.commit()

def is_share_received(share_code):
    cursor.execute("SELECT 1 FROM received_shares WHERE share_code=?", (share_code,))
    return cursor.fetchone() is not None

def mark_share_received(share_code, receive_code, txt_file, cid):
    cursor.execute(
        "INSERT OR REPLACE INTO received_shares (share_code, receive_code, txt_file, cid) VALUES (?, ?, ?, ?)",
        (share_code, receive_code, txt_file, cid)
    )
    conn.commit()

# 配置：更新正则表达式以匹配所有可能的链接格式
link_pattern = re.compile(r'https://(115cdn\.com|anxia\.com|115\.com)/s/(\w+)\?password=(\w+)(?:#.*)?')

txt_directory_path = "./links"
txt_files = [f for f in os.listdir(txt_directory_path) if f.endswith('.txt')]

print(f"📁 检测到 {len(txt_files)} 个txt分享文件")

# 遍历每个txt
for txt_file in txt_files:
    if txt_file not in txt_to_cid_map:
        print(f"⚠️ 未在映射表中找到 {txt_file}，跳过")
        continue

    target_cid = txt_to_cid_map[txt_file]
    txt_file_path = os.path.join(txt_directory_path, txt_file)
    print(f"\n📂 处理文件：{txt_file} → 保存到目录 CID：{target_cid}")

    with open(txt_file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    for line in lines:
        print(f"🧪 扫描行：{line.strip()}")
        match = link_pattern.search(line)
        if not match:
            continue

        old_link = match.group(1)  # 获取旧链接
        share_code = match.group(2)
        receive_code = match.group(3)

        # 替换旧链接为新链接
        new_link = old_link.replace('115.com', '115cdn.com').replace('anxia.com', '115cdn.com')

        if is_share_received(share_code):
            print(f"🔁 已转存过的分享：{share_code}，跳过")
            continue

        try:
            payload = {
                "share_code": share_code,
                "receive_code": receive_code,
                "file_id": "0",  # 接收全部
                "cid": target_cid
            }

            # 将新的链接传给客户端进行转存
            response = client.share_receive(payload)
            if response.get('state', False):
                print(f"✅ 成功转存分享：{share_code}")
                mark_share_received(share_code, receive_code, txt_file, target_cid)
            else:
                print(f"❌ 转存失败：{share_code} → 错误：{response.get('error_msg', '未知错误')}")
        except Exception as e:
            print(f"❌ 异常：{share_code} → {e}")

# 清理
conn.close()
