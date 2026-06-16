import requests
from bs4 import BeautifulSoup
import csv
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime
import asyncio
from playwright.async_api import async_playwright

CSV_FILE = "data.csv"
TODAY = datetime.now().strftime("%Y-%m-%d")

MOVIE_NAME = "グレイ・ミッション"
FILMARKS_URL = "https://filmarks.com/movies/128389"
EIGA_URL = "https://eiga.com/movie/106214/users/"


async def get_filmarks_mark_count():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        await page.goto(FILMARKS_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(8000)

        count = None

        # クリップ数（見たい人数）を取得
        try:
            el = page.locator(".c-content__action--clips .c-content__count").first
            text = await el.text_content(timeout=5000)
            nums = re.findall(r"[\d,]+", text)
            if nums:
                count = int(nums[0].replace(",", ""))
                print(f"[Filmarks] クリップ数取得成功: {count}")
        except Exception as e:
            print(f"[Filmarks] クリップ数取得失敗: {e}")

        await browser.close()
        return count


def get_eiga_checkin_count():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(EIGA_URL, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text()
    match = re.search(r"Check-inしたユーザー（(\d+)人）", text)
    return int(match.group(1)) if match else None


def save_to_csv(filmarks_count, eiga_count):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["date", "filmarks_clip_count", "eiga_checkin_count"])
        writer.writerow([TODAY, filmarks_count, eiga_count])
    print(f"CSV保存完了: {TODAY}, Filmarks={filmarks_count}, eiga={eiga_count}")


def send_email(filmarks_count, eiga_count):
    gmail_user = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]
    email_to = os.environ["EMAIL_TO"]

    msg = MIMEMultipart()
    msg["From"] = gmail_user
    msg["To"] = email_to
    msg["Subject"] = f"[{MOVIE_NAME}] {TODAY} の記録"

    fm_str = f"{filmarks_count:,}" if filmarks_count is not None else "取得失敗"
    eiga_str = f"{eiga_count:,}" if eiga_count is not None else "取得失敗"

    body = f"""本日（{TODAY}）の{MOVIE_NAME}データをお届けします。

■ Filmarks クリップ数: {fm_str} 人（見たい）
■ eiga.com Check-in数: {eiga_str} 人（見た）

累積データのCSVを添付しています。
"""
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with open(CSV_FILE, "rb") as f:
        attachment = MIMEBase("application", "octet-stream")
        attachment.set_payload(f.read())
        encoders.encode_base64(attachment)
        attachment.add_header(
            "Content-Disposition",
            "attachment",
            filename=("utf-8", "", f"{MOVIE_NAME}.csv")
        )
        msg.attach(attachment)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.send_message(msg)
    print(f"メール送信完了 → {email_to}")


async def main():
    print(f"=== {TODAY} データ取得開始 ===")

    filmarks_count = await get_filmarks_mark_count()
    print(f"Filmarks マーク数: {filmarks_count}")

    eiga_count = get_eiga_checkin_count()
    print(f"eiga.com Check-in数: {eiga_count}")

    save_to_csv(filmarks_count, eiga_count)
    send_email(filmarks_count, eiga_count)

    print("=== 完了 ===")


if __name__ == "__main__":
    asyncio.run(main())
