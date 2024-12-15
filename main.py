from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from google.cloud import aiplatform
from PyPDF2 import PdfReader

app = Flask(__name__)

# ค่า credentials จาก LINE Developer Console
LINE_CHANNEL_SECRET = '5c8d2c4b41d6307b5df9f14ca01bb1df'
LINE_CHANNEL_ACCESS_TOKEN = 'S57WX85ldXlMWLDXqYMgwAFRFVsQ9PYjIzp5Ov8d1YV+U6yHvClLTqDAsUx2XZ8zMJdNlyztCGX+Qd+r9Hjaw4wYliM3cU4er6H57nlhIhE1mwSYDobeic8pk3igOO1JWhy/3TJd7iu9icbEeWrsdQdB04t89/1O/w1cDnyilFU='

# ค่า project จาก Google Cloud
PROJECT_ID = 'lexical-period-444405-e3'
LOCATION = 'us-central1'

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
        print(f"Error reading PDF: {e}")
        return ""


# อ่าน PDF ตั้งแต่เริ่มต้น
PDF_CONTENT = extract_pdf_content()


def get_vertex_ai_response(question):
    try:
        # สร้าง prompt ที่รวม context จาก PDF
        prompt = f"""
        คุณเป็น AI ที่ช่วยอ่านเอกสารและตอบคำถามเกี่ยวกับข้อมูลในเอกสาร กรุณาตอบคำถามอย่างกระชับและตรงประเด็น หากไม่มีข้อมูลในเอกสาร ให้แจ้งว่าไม่พบข้อมูลดังกล่าว

        เอกสาร:
        {PDF_CONTENT}

        คำถาม: {question}
        คำตอบ:
        """

        endpoint = f"projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/gemini-1.5-flash-002"
        response = aiplatform.predict(
            endpoint=endpoint,
            instances=[{"prompt": prompt}]
        )
        return response
    except Exception as e:
        print(f"Error getting response from Vertex AI: {e}")
        return "ขออภัย ไม่สามารถประมวลผลคำถามได้ในขณะนี้"


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
    response = get_vertex_ai_response(user_question)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response)
    )


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)