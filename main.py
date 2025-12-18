import asyncio
import re
import smtplib
import os
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from playwright.async_api import async_playwright

# ================= 📧 环境变量配置区域 =================
# 从 GitHub Secrets 读取配置
EMAIL_CONFIG = {
    "sender": os.environ.get("MAIL_SENDER"),
    "password": os.environ.get("MAIL_PASSWORD"),
    "receiver": os.environ.get("MAIL_RECEIVER"),
    "smtp_server": "smtp.qq.com",
    "smtp_port": 465
}

SOURCE_URL = "https://sitson.pages.dev/p"
# =================================================

def send_consolidated_email(available_list):
    """
    发送汇总邮件
    """
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

async def fetch_activity_links(page):
    """
    从源网页提取所有活动链接
    """
    print(f"正在获取任务列表: {SOURCE_URL} ...")
    try:
        await page.goto(SOURCE_URL, wait_until="domcontentloaded")
        
        # 等待内容加载 (最多等10秒)
        try:
            await page.wait_for_selector("#textDisplay", timeout=10000)
            await page.wait_for_timeout(3000) # 额外等3秒确保API返回
        except:
            print("❌ 获取任务列表超时，页面可能未加载完成")
            return []
        
        content = await page.locator("#textDisplay").inner_text()
        
        if not content:
            print("⚠️ 任务列表为空")
            return []

        # 提取链接
        urls = re.findall(r'https?://[^\s,;"\'<>]+', content)
        activity_links = [u for u in urls if "http" in u]
        
        print(f"✅ 提取到 {len(activity_links)} 个链接。")
        return list(set(activity_links)) # 去重

    except Exception as e:
        print(f"❌ 获取链接列表失败: {e}")
        return []

async def check_single_url(page, url):
    """
    检测单个链接的状态
    """
    print(f"正在检查: {url}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        
        try:
            await page.wait_for_selector("text=已报人数", timeout=5000)
        except:
            print("  -> 跳过 (非活动页面或加载慢)")
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
        
        return 0
            
    except Exception as e:
        print(f"  -> 检查出错: {e}")
        return 0

async def main():
    print("程序启动...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 1. 获取链接
        links = await fetch_activity_links(page)
        
        if not links:
            print("没有找到链接，任务结束。")
            await browser.close()
            return

        # 2. 逐个检查
        found_activities = []
        for link in links:
            spots = await check_single_url(page, link)
            if spots > 0:
                found_activities.append({"url": link, "spots": spots})
            await asyncio.sleep(1) # 防封IP

        # 3. 发送汇总邮件
        if found_activities:
            send_consolidated_email(found_activities)
        else:
            print("本次巡检结束，所有活动已满员。")

        await browser.close()

if __name__ == "__main__":
    # 简单的环境变量检查
    if not EMAIL_CONFIG["password"]:
        print("❌ 错误：未读取到密码，请检查 GitHub Secrets 配置。")
    else:
        asyncio.run(main())
