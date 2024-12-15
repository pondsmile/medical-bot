import os
import logging
import re
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from PyPDF2 import PdfReader
import google.generativeai as genai

# ตั้งค่า logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# LINE Credentials
LINE_CHANNEL_SECRET = '5c8d2c4b41d6307b5df9f14ca01bb1df'
LINE_CHANNEL_ACCESS_TOKEN = 'S57WX85ldXlMWLDXqYMgwAFRFVsQ9PYjIzp5Ov8d1YV+U6yHvClLTqDAsUx2XZ8zMJdNlyztCGX+Qd+r9Hjaw4wYliM3cU4er6H57nlhIhE1mwSYDobeic8pk3igOO1JWhy/3TJd7iu9icbEeWrsdQdB04t89/1O/w1cDnyilFU='
GEMINI_API_KEY = "AIzaSyAvfgYbn-zTam2NcgSND6vgJ6wonObZOYY"

# ตั้งค่า Gemini AI
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Global variables
PDF_CONTENT = None
GEMINI_MODEL = None
USER_CONTEXTS = {}


def extract_pdf_content():
    try:
        reader = PdfReader("data/hospital_rates.pdf")
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        logging.error(f"Error reading PDF: {e}")
        return ""


def is_relevant_question(question, pdf_content):
    # สร้าง prompt เพื่อตรวจสอบความเกี่ยวข้องกับ PDF
    check_prompt = f"""
    ประเมินว่าคำถามต่อไปนี้เกี่ยวข้องกับเนื้อหาใน PDF หรือไม่:

    คำถาม: {question}

    เนื้อหา PDF:
    {pdf_content[:1000]}  # ใช้เพียงบางส่วนเพื่อประหยัดโควตา

    ตอบเพียง "ใช่" หากคำถามเกี่ยวข้องกับเนื้อหาใน PDF 
    ตอบเพียง "ไม่" หากคำถามไม่เกี่ยวข้อง
    """

    try:
        check_model = genai.GenerativeModel('gemini-pro')
        response = check_model.generate_content(check_prompt)

        # ตรวจสอบคำตอบ
        answer = response.text.strip().lower()
        return "ใช่" in answer
    except Exception as e:
        logging.error(f"Error checking question relevance: {e}")
        return False


def initialize_ai_model(user_id):
    global PDF_CONTENT, GEMINI_MODEL

    # โหลด PDF เพียงครั้งเดียว
    if PDF_CONTENT is None:
        PDF_CONTENT = extract_pdf_content()

    # สร้าง model
    generation_config = {
        "temperature": 0.2,
        "top_p": 0.8,
        "max_output_tokens": 2048,
    }

    GEMINI_MODEL = genai.GenerativeModel(
        model_name="gemini-pro",
        generation_config=generation_config,
    )

    # เตรียม initial prompt
    initial_prompt = f"""
    คุณเป็น AI ผู้ช่วยที่ให้ข้อมูลเฉพาะจากเอกสารบริการทางการแพทย์เท่านั้น

    กฎสำคัญ:
    1. ตอบเฉพาะคำถามที่เกี่ยวข้องกับเนื้อหาใน PDF นี้
    2. หากไม่มีข้อมูลในเอกสาร ให้ตอบว่า "ขออภัย ไม่พบข้อมูลที่ตรงกับคำถาม"
    3. ห้ามตอบคำถามที่อยู่นอกเหนือเอกสาร

    ข้อมูลในเอกสาร:
    {PDF_CONTENT}
    """

    # สร้าง chat session สำหรับผู้ใช้แต่ละคน
    user_contexts = GEMINI_MODEL.start_chat(history=[
        {"role": "user", "parts": [initial_prompt]},
        {"role": "model", "parts": ["เข้าใจแล้วค่ะ จะตอบเฉพาะข้อมูลใน PDF"]}
    ])

    # บันทึก context ของผู้ใช้
    USER_CONTEXTS[user_id] = user_contexts
    return user_contexts


def get_gemini_response(user_id, question):
    global PDF_CONTENT
    try:
        # ตรวจสอบความเกี่ยวข้องของคำถาม
        if not is_relevant_question(question, PDF_CONTENT):
            return "ขออภัย สามารถสอบถามเฉพาะข้อมูลจากเอกสารบริการทางการแพทย์เท่านั้นค่ะ"

        # ตรวจสอบ context ของผู้ใช้
        if user_id not in USER_CONTEXTS:
            chat_session = initialize_ai_model(user_id)
        else:
            chat_session = USER_CONTEXTS[user_id]

        # ส่งคำถาม
        response = chat_session.send_message(question)
        return response.text

    except Exception as e:
        logging.error(f"Error getting response from Gemini AI: {e}")

        # หากเกิด quota error หรือ rate limit
        if "429" in str(e) or "Resource has been exhausted" in str(e):
            return "ขออภัย ระบบกำลังมีผู้ใช้งานหนาแน่น กรุณารอสักครู่แล้วลองใหม่อีกครั้งค่ะ"

        return "ขออภัย ไม่สามารถประมวลผลคำถามได้ในขณะนี้ค่ะ"


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_question = event.message.text
    logging.info(f"Received message from {user_id}: {user_question}")

    try:
        # ส่งข้อความรอก่อน
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="กรุณารอสักครู่ กำลังประมวลผล...")
        )

        # ประมวลผลคำตอบ
        response = get_gemini_response(user_id, user_question)
        logging.info(f"Generated response: {response}")

        # ส่งคำตอบกลับ
        line_bot_api.push_message(
            user_id,
            TextSendMessage(text=response)
        )

    except Exception as e:
        logging.error(f"Error handling message: {e}")
        line_bot_api.push_message(
            user_id,
            TextSendMessage(text="ขออภัย เกิดข้อผิดพลาดในการประมวลผล")
        )


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)