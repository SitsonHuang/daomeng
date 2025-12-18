import asyncio
import re
import smtplib
import os
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from playwright.async_api import async_playwright

# ================= 📧 环境变量配置区域 =================
# 必须从环境变量读取，不能写死在代码里
EMAIL_CONFIG = {
    "sender": os.environ.get("MAIL_SENDER"),
    "password": os.environ.get("MAIL_PASSWORD"),
    "receiver": os.environ.get("MAIL_RECEIVER"),
    "smtp_server": "smtp.qq.com",
    "smtp_port": 465
}

SOURCE_URL = "https://sitson.pages.dev/p"
# =================================================

# --- 函数 1: 发送邮件 ---
def send_consolidated_email(available_list):
    if not available_list:
        return

    try:
        print(f"正在发送汇总邮件给 {EMAIL_CONFIG['receiver']} ...")
        
        items_html = ""
        for item in available_list:
            items_html += f"""
            <div style="border:1px solid #ddd; padding:10px; margin-bottom:10px; border-radius:5px;">
                <p><b>活动链接：</b><a href="{item['url']}">{item['url']}</a></p>
                <p>剩余名额：<span style="color:red; font-weight:bold;">{item['spots']}</span> 个</p>
            </div>
            """

        mail_content = f"""
        <h1>🎉 发现 {len(available_list)} 个活动有名额！</h1>
        <p>以下活动检测到空缺，请尽快操作：</p>
        {items_html}
        <p style="color:gray; font-size:12px;">此邮件由 Python 自动化脚本发送</p>
        """
        
        message = MIMEText(mail_content, 'html', 'utf-8')
        message['From'] = formataddr(["抢票助手", EMAIL_CONFIG["sender"]])
        message['To'] = formataddr(["管理员", EMAIL_CONFIG["receiver"]])
        message['Subject'] = Header(f"【紧急】发现 {len(available_list)} 个可用活动！", 'utf-8')

        server = smtplib.SMTP_SSL(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"])
        server.login(EMAIL_CONFIG["sender"], EMAIL_CONFIG["password"])
        server.sendmail(EMAIL_CONFIG["sender"], [EMAIL_CONFIG["receiver"]], message.as_string())
        server.quit()
        print(f"✅ 汇总邮件发送成功！")
        
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

# --- 函数 2: 获取链接列表 ---
async def fetch_activity_links(page):
    print(f"正在获取任务列表: {SOURCE_URL} ...")
    try:
        await page.goto(SOURCE_URL, wait_until="domcontentloaded")
        
        try:
            # 等待文本框出现
            await page.wait_for_selector("#textDisplay", timeout=10000)
            # 额外等待3秒让JS渲染内容
            await page.wait_for_timeout(3000) 
        except:
            print("❌ 获取任务列表超时")
            return []
        
        content = await page.locator("#textDisplay").inner_text()
        
        if not content:
            print("⚠️ 任务列表为空")
            return []

        urls = re.findall(r'https?://[^\s,;"\'<>]+', content)
        activity_links = [u for u in urls if "http" in u]
        
        print(f"✅ 提取到 {len(activity_links)} 个链接。")
        return list(set(activity_links))

    except Exception as e:
        print(f"❌ 获取链接列表失败: {e}")
        return []

# --- 函数 3: 检查单个链接 ---
async def check_single_url(page, url):
    print(f"正在检查: {url}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        
        try:
            await page.wait_for_selector("text=已报人数", timeout=5000)
        except:
            print("  -> 跳过 (非活动页面或加载超时)")
            return 0
            
        html_content = await page.content()
        match = re.search(r"已报人数：(\d+)/(\d+)", html_content)
        
        if match:
            registered = int(match.group(1))
            maximum = int(match.group(2))
            
            if registered < maximum:
                left = maximum - registered
                print(f"  -> ✅ 发现名额！剩余 {left} 个")
                return left
            else:
                print(f"  -> ❌ 名额已满 ({registered}/{maximum})")
                return 0
        return 0
            
    except Exception as e:
        print(f"  -> 检查出错: {e}")
        return 0

# --- 主程序 ---
async def main():
    print("程序启动...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 调用函数2
        links = await fetch_activity_links(page)
        
        if not links:
            print("没有找到链接，任务结束。")
            await browser.close()
            return

        found_activities = []
        for link in links:
            # 调用函数3
            spots = await check_single_url(page, link)
            if spots > 0:
                found_activities.append({"url": link, "spots": spots})
            await asyncio.sleep(1)

        if found_activities:
            # 调用函数1
            send_consolidated_email(found_activities)
        else:
            print("本次巡检结束，所有活动已满员。")

        await browser.close()

if __name__ == "__main__":
    if not EMAIL_CONFIG["password"]:
        print("❌ 错误：环境变量未配置！")
    else:
        asyncio.run(main())
