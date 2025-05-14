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

# 更稳健的正则：分别提取链接和提取码
link_re = re.compile(r'https?://(?:115cdn\.com|anxia\.com|115\.com)/s/(\w+)', re.IGNORECASE)
code_re = re.compile(r'提取码[:：]?\s*(\w{4})', re.IGNORECASE)

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

        link_match = link_re.search(line)
        code_match = code_re.search(line)

        if not link_match:
            continue

        share_code = link_match.group(1)
        receive_code = code_match.group(1) if code_match else None

        if not receive_code:
            print(f"⚠️ 找不到提取码，跳过分享：{share_code}")
            continue

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

            # 调用 API 执行转存
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
