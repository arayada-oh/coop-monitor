import os
import datetime
import requests
import pandas as pd
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ดึงค่าการเชื่อมต่อคลาวด์จาก GitHub Secrets
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")      # Gmail ผู้ส่ง
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")  # รหัสผ่านแอป 16 หลัก
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")  # อีเมลผู้รับ

# ลิงก์แปลง Google Sheets เป็น CSV
GOOGLE_SHEET_URL = f"https://google.com{SHEET_ID}/export?format=csv"

def send_email_notify(subject, body_text):
    """ฟังก์ชันสำหรับส่งอีเมลแจ้งเตือนผ่าน Gmail SMTP"""
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        print("ข้อผิดพลาด: ตั้งค่าตัวแปรอีเมลไม่ครบ ข้ามการส่ง")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = subject
    msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
    
    try:
        server = smtplib.SMTP('://gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
        print(f"📧 ส่งอีเมลแจ้งเตือนสำเร็จหัวข้อ: {subject}")
    except Exception as e:
        print(f"ไม่สามารถส่งอีเมลได้: {e}")

def main():
    if not SHEET_ID:
        print("ข้อผิดพลาด: ไม่ได้ตั้งค่า GOOGLE_SHEET_ID")
        return

    try:
        df = pd.read_csv(GOOGLE_SHEET_URL)
        df['Expected_Date'] = pd.to_datetime(df['Expected_Date'])
    except Exception as e:
        print(f"ไม่สามารถโหลดข้อมูลจาก Google Sheets ได้: {e}")
        return

    today = datetime.datetime.now()
    print(f"เวลาปัจจุบันของระบบ: {today.strftime('%Y-%m-%d %H:%M:%S')}")

    for index, row in df.iterrows():
        coop_name = row['Coop_Name']
        url = row['URL']
        expected_date = row['Expected_Date']
        user_status = str(row['User_Status']).strip()
        already_notified = str(row['Already_Notified']).strip().upper()

        # กฎข้อที่ 1: ตรวจสอบการหยุดทำงานโดยผู้ใช้ (Done)
        if user_status == "Done":
            print(f"[-] {coop_name}: ข้ามการสแกน (คุณเปลี่ยนสถานะเป็น Done แล้ว)")
            continue

        # คำนวณช่วงเวลาเริ่มทำงานล่วงหน้า 2 เดือน (60 วัน)
        start_monitoring_date = expected_date - datetime.timedelta(days=60)

        # กฎข้อที่ 2: ทำงานในหน้าต่างเวลาล่วงหน้า 2 เดือน
        if today >= start_monitoring_date:
            # กฎข้อที่ 3: ป้องกันการส่งอีเมลซ้ำซ้อนทุกวัน
            if already_notified == "TRUE":
                print(f"[~] {coop_name}: ตรวจเจอคำสำคัญก่อนหน้านี้แล้ว (รอคุณตรวจสอบบน Google Sheets)")
                continue

            print(f"[+] กำลังสแกน: {coop_name} -> {url}")
            
            try:
                res = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                res.encoding = 'utf-8'
                
                soup = BeautifulSoup(res.text, 'html.parser')
                web_text = soup.get_text()
                
                keywords = ["ประกันกลุ่ม", "ประกันชีวิตกลุ่ม", "รายชื่อประกัน"]
                
                if any(kw in web_text for kw in keywords):
                    subject = f"🔔 [พบสิ่งน่าสงสัย] ประกาศประกันกลุ่ม - {coop_name}"
                    body_text = (
                        f"ระบบตรวจพบคำคีย์เวิร์ดในหน้าเว็บของ {coop_name}\n\n"
                        f"🔗 ลิงก์หน้าประกาศ: {url}\n\n"
                        f"ขั้นตอนการจัดการ:\n"
                        f"1. กรุณากดลิงก์ด้านบนเพื่อตรวจสอบว่าเป็นประกาศจริงรอบปีนี้หรือไม่\n"
                        f"2. หากใช่ประกาศจริง: ให้ไปเปลี่ยนช่อง User_Status เป็น 'Done' ใน Google Sheets เพื่อหยุดการทำงานถาวร\n"
                        f"3. หากไม่ใช่ประกาศจริง: ให้เปลี่ยนช่อง Already_Notified เป็น 'TRUE' ใน Google Sheets เพื่อไม่ให้ระบบส่งอีเมลเตือนซ้ำในวันพรุ่งนี้"
                    )
                    send_email_notify(subject, body_text)
                else:
                    print(f"    -> สแกนแล้ว ยังไม่พบคีย์เวิร์ดใหม่")
                    
            except Exception as e:
                print(f"เกิดข้อผิดพลาดในการเปิดเว็บ {coop_name}: {e}")
        else:
            days_left = (start_monitoring_date - today).days
            print(f"[*] {coop_name}: ยังไม่ถึงเวลาสแกน (จะเริ่มสแกนในอีก {days_left} วัน)")

if __name__ == "__main__":
    main()
