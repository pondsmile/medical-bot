import os
import logging
from flask import Flask, request, abort
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest
from linebot.v3.webhook import WebhookHandler, WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    Event,
    MessageEvent,
    TextMessageContent
)
from google.cloud import aiplatform
import pdfminer.high_level

# ตั้งค่า logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# LINE Credentials
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET', '5c8d2c4b41d6307b5df9f14ca01bb1df')
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', 'S57WX85ldXlMWLDXqYMgwAFRFVsQ9PYjIzp5Ov8d1YV+U6yHvClLTqDAsUx2XZ8zMJdNlyztCGX+Qd+r9Hjaw4wYliM3cU4er6H57nlhIhE1mwSYDobeic8pk3igOO1JWhy/3TJd7iu9icbEeWrsdQdB04t89/1O/w1cDnyilFU=')

# ตั้งค่า LINE Bot
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
parser = WebhookParser(LINE_CHANNEL_SECRET)

# Google Cloud Project
PROJECT_ID = os.environ.get('PROJECT_ID', 'lexical-period-444405-e3')
LOCATION = os.environ.get('LOCATION', 'us-central1')


def extract_pdf_content():
    """แยกข้อความจากไฟล์ PDF"""
    try:
        logger.info("เริ่มอ่านไฟล์ PDF")
        # ตรวจสอบว่ามีไฟล์จริง
        pdf_path = "data/hospital_rates.pdf"
        if not os.path.exists(pdf_path):
            logger.error(f"ไม่พบไฟล์ PDF ที่ {pdf_path}")
            return ""

        # ใช้ pdfminer เพื่อดึงข้อความ
        with open(pdf_path, 'rb') as file:
            text = pdfminer.high_level.extract_text(file)

        logger.info(f"อ่านไฟล์ PDF สำเร็จ ความยาว: {len(text)} ตัวอักษร")
        return text
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์ PDF: {e}")
        return ""


# โหลดเนื้อหา PDF
PDF_CONTENT = extract_pdf_content()


def get_vertex_ai_response(question):
    """รับการตอบกลับจาก Vertex AI"""
    try:
        logger.info(f"รับคำถาม: {question}")

        # สร้าง prompt
        prompt = f"""
        คุณเป็น AI ผู้ช่วยที่ช่วยอ่านข้อมูลเอกสารและตอบคำถามเกี่ยวกับข้อมูลในเอกสาร 
        ให้คุณตอบคำถามด้วยภาษาพูดที่สุภาพและกระชับ โดยไม่ต้องอ้างอิงว่ามาจากเอกสาร 
        ตอบตรงคำถาม 

        ข้อมูลในเอกสาร:
        {PDF_CONTENT}

        คำถาม: {question}
        คำตอบ:
        """

        # ตรวจสอบ endpoint
        endpoint = f"projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/gemini-1.5-flash-002"
        logger.info(f"Endpoint: {endpoint}")

        # สร้าง Vertex AI client
        client = aiplatform.gapic.PredictionServiceClient()
        instance = {"prompt": prompt}

        logger.info("กำลังส่งคำขอไปยัง Vertex AI")

        # ส่งคำขอไปยัง Vertex AI
        try:
            response = client.predict(
                endpoint=endpoint,
                instances=[instance],
                parameters={}
            )
        except Exception as ai_error:
            logger.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ Vertex AI: {ai_error}")
            return "ขออภัย ระบบ AI ขัดข้องค่ะ"

        logger.info("ได้รับการตอบกลับจาก Vertex AI")

        # ตรวจสอบผลลัพธ์
        if response and response.predictions:
            result = response.predictions[0].get("text", "ขออภัย ไม่สามารถประมวลผลคำถามได้ในขณะนี้ค่ะ")
            logger.info(f"ผลลัพธ์: {result}")
            return result
        else:
            logger.warning("ไม่พบข้อมูลการตอบกลับจาก Vertex AI")
            return "ขออภัย ไม่สามารถประมวลผลคำถามได้ในขณะนี้ค่ะ"

    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการรับการตอบกลับจาก Vertex AI: {e}")
        return "ขออภัย เกิดข้อผิดพลาดในการประมวลผลค่ะ"


@app.route("/callback", methods=['POST'])
def callback():
    """จัดการ webhook จาก LINE"""
    try:
        # ตรวจสอบ signature
        signature = request.headers['X-Line-Signature']
        body = request.get_data(as_text=True)
        logger.info(f"ได้รับ signature: {signature}")
        logger.info(f"เนื้อหาข้อความ: {body}")

        # ประมวลผล webhook
        events = parser.parse(body, signature)

        for event in events:
            if isinstance(event, MessageEvent):
                if isinstance(event.message, TextMessageContent):
                    handle_message(event)

        return 'OK'
    except (InvalidSignatureError, Exception) as e:
        logger.error(f"เกิดข้อผิดพลาดใน webhook: {e}")
        abort(400)


def handle_message(event):
    """จัดการข้อความจาก LINE"""
    try:
        # รับข้อความจากผู้ใช้
        user_question = event.message.text
        logger.info(f"ได้รับข้อความจาก LINE: {user_question}")

        # ส่งคำถามไปยัง Vertex AI เพื่อรับคำตอบ
        response = get_vertex_ai_response(user_question)
        logger.info(f"กำลังส่งข้อความกลับ: {response}")

        # ส่งข้อความกลับไปยัง LINE
        line_bot_api.reply_message(
            ReplyMessageRequest(
                replyToken=event.reply_token,
                messages=[response]
            )
        )
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการจัดการข้อความ: {e}")
        # ส่งข้อความแจ้งข้อผิดพลาดกลับให้ผู้ใช้
        line_bot_api.reply_message(
            ReplyMessageRequest(
                replyToken=event.reply_token,
                messages=["ขออภัย เกิดข้อผิดพลาดในการประมวลผลข้อความค่ะ"]
            )
        )


if __name__ == "__main__":
    logger.info("เริ่มต้นแอปพลิเคชัน")
    app.run(host='0.0.0.0', port=8080)