import os
import logging
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


# Load PDF content
PDF_CONTENT = extract_pdf_content()


def get_gemini_response(question):
    try:
        # กำหนดค่าการสร้างข้อความ
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 2048,
        }

        # สร้างโมเดล
        model = genai.GenerativeModel(
            model_name="gemini-pro",
            generation_config=generation_config,
        )

        # สร้างพร้อมท์
        prompt = f"""
        คุณเป็น AI ผู้ช่วยที่ช่วยอ่านข้อมูลเอกสารและตอบคำถามเกี่ยวกับข้อมูลในเอกสาร 
        ให้คุณตอบคำถามด้วยภาษาพูดที่สุภาพและกระชับ โดยไม่ต้องอ้างอิงว่ามาจากเอกสาร 
        ตอบตรงคำถาม เช่น:
        - หากถาม \"ราคานี้เท่าไหร่?\" ให้ตอบ \"ราคาที่คุณถามอยู่ 150 บาทค่ะ\"
        - หากถาม \"เวลาทำการคือกี่โมง?\" ให้ตอบ \"8 โมงเช้าถึง 5 โมงเย็นค่ะ\"
        ข้อมูลในเอกสาร:
        {PDF_CONTENT}
        คำถาม: {question}
        คำตอบ:
        """

        # เริ่มเซสชันแชท
        chat_session = model.start_chat(history=[])

        # ส่งคำถาม
        response = chat_session.send_message(prompt)

        return response.text

    except Exception as e:
        logging.error(f"Error getting response from Gemini AI: {e}")
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
    user_question = event.message.text
    logging.info(f"Received message: {user_question}")

    try:
        response = get_gemini_response(user_question)
        logging.info(f"Generated response: {response}")

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=response)
        )
    except Exception as e:
        logging.error(f"Error handling message: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="ขออภัย เกิดข้อผิดพลาดในการประมวลผล")
        )


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)