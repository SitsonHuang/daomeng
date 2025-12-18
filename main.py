import asyncio
import re
import smtplib
import os  # <--- 新增：用于读取环境变量
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from playwright.async_api import async_playwright

# ================= 📧 环境变量配置区域 =================
# 我们不再这里硬编码，而是从系统环境读取
# 如果本地运行报错，请在终端先 export 变量，或者临时写死测试
EMAIL_CONFIG = {
    "sender": os.environ.get("MAIL_SENDER"),      # 从GitHub Secrets读取
    "password": os.environ.get("MAIL_PASSWORD"),  # 从GitHub Secrets读取
    "receiver": os.environ.get("MAIL_RECEIVER"),  # 从GitHub Secrets读取
    "smtp_server": "smtp.qq.com",
    "smtp_port": 465
}

SOURCE_URL = "https://sitson.pages.dev/p"
# =================================================

# ... (中间的 send_consolidated_email, fetch_activity_links, check_single_url 函数保持不变，直接复制之前的即可) ...
# ... (为节省篇幅，这里省略中间函数，请务必保留之前的逻辑) ...

async def main():
    # ... (保持之前的 main 逻辑不变) ...
    # 稍微加一个 print 方便调试 Action
    print("程序启动...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        links = await fetch_activity_links(page)
        
        if not links:
            print("没有找到链接")
            await browser.close()
            return

        found_activities = []
        for link in links:
            spots = await check_single_url(page, link)
            if spots > 0:
                found_activities.append({"url": link, "spots": spots})
            await asyncio.sleep(1) 

        if found_activities:
            send_consolidated_email(found_activities)
        else:
            print("所有活动已满。")

        await browser.close()

if __name__ == "__main__":
    # 简单检查环境变量是否存在
    if not EMAIL_CONFIG["password"]:
        print("❌ 错误：未检测到环境变量 MAIL_PASSWORD。")
        print("如果是本地运行，请手动填入；如果是GitHub Actions，请检查Secrets设置。")
    else:
        asyncio.run(main())
