# ใช้ Python 3.9 เป็นฐาน
FROM python:3.9-slim

# ตั้งค่าโฟลเดอร์ทำงาน
WORKDIR /app

# Copy requirements.txt ไปก่อน
COPY requirements.txt .

# ติดตั้ง Python packages
RUN pip install -r requirements.txt

# Copy ไฟล์ทั้งหมดที่เหลือ
COPY . .

# ตั้งค่า port
ENV PORT 8080

# รันแอพ
CMD ["python", "main.py"]