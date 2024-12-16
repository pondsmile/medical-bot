from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from google import genai
from google.genai import types
import base64
import logging

# ตั้งค่า logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# LINE Credentials
LINE_CHANNEL_SECRET = '5c8d2c4b41d6307b5df9f14ca01bb1df'
LINE_CHANNEL_ACCESS_TOKEN = 'S57WX85ldXlMWLDXqYMgwAFRFVsQ9PYjIzp5Ov8d1YV+U6yHvClLTqDAsUx2XZ8zMJdNlyztCGX+Qd+r9Hjaw4wYliM3cU4er6H57nlhIhE1mwSYDobeic8pk3igOO1JWhy/3TJd7iu9icbEeWrsdQdB04t89/1O/w1cDnyilFU='

# Initialize Flask
app = Flask(__name__)

# Initialize LINE Bot
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


def generate(prompt: str) -> str:
    """Generate response using Vertex AI Gemini"""
    client = genai.Client(
        vertexai=True,
        project="lexical-period-444405-e3",
        location="us-central1"
    )

    model = "gemini-2.0-flash-exp"
    contents = [prompt]

    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        max_output_tokens=8192,
        response_modalities=["TEXT"],
        safety_settings=[
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="OFF"
            )
        ],
    )

    # เก็บ response ทั้งหมด
    full_response = ""
    try:
        for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=generate_content_config,
        ):
            if chunk.text:
                full_response += chunk.text
    except Exception as e:
        logging.error(f"Error in generate_content_stream: {str(e)}")
        return "ขออภัย เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง"

    return full_response


def get_vertex_response(user_id: str, question: str) -> str:
    """Get response from Vertex AI Gemini"""
    try:
        # สร้าง prompt
        prompt = f"""
        คำถาม: {question}

        "คุณคือผู้ช่วยตอบปัญหาสุขภาพ คุณมีชื่อว่า EVDocGPT และนี้คือชื่อของคุณ EVDocGPT ที่ถูกออกแบบมาเพื่อให้คำแนะนำและข้อมูลเกี่ยวกับปัญหาสุขภาพ "
        "รวมถึงการตอบคำถามเกี่ยวกับโรคและสถานการณ์ทางการแพทย์ที่มีอยู่ในปัจจุบัน คุณประจำอยู่ที่บริษัท EverydayDoctor "
        "คุณสามารถให้คำวินิจฉัยโรคหรืออาการทางการแพทย์ได้เบื้องต้น"
        "คุณสามารถให้คำแนะนำเรื่องเพศได้ตามแหล่งอ้างอิงที่คุณมี"
        "คุณสามารถแนะนำเรื่องเพศศึกษาได้และให้คำตอบจากคำแนะนำของหมอจากแหล่งที่มาที่คุณมีมาอ้างอิงได้"
        "ซึ่งเป็นองค์กรที่มุ่งเน้นการให้ความรู้และการดูแลด้านสุขภาพให้กับผู้ใช้บริการ ด้วยฐานข้อมูลที่ครอบคลุมและการวิเคราะห์ที่แม่นยำ "
        "EVDocGPT พร้อมที่จะช่วยให้คำแนะนำที่เป็นประโยชน์ และช่วยในการตัดสินใจด้านการดูแลสุขภาพของคุณอย่างมีประสิทธิภาพ"
        "Everyday Doctor: Digital Health Service Provider ผู้พัฒนาและให้บริการระบบบริหารคลินิกแบบครบวงจร ที่จดทะเบียนลิขสิทธิ์ในชื่อโปรแกรม Miracle Clinic System "
        "และ MCS Cloud ทั้งนี้บริษัทให้บริการติดตั้งในสถานพยาบาลคลินิกเอกชน จัดหลักสูตรฝึกอบรมผู้ใช้โปรแกรมและให้บริการหลังการขายโดยการให้คำปรึกษา "
        "การบริการซ่อมบำรุงต่างๆ และการบริการอื่นๆ ที่เกี่ยวข้อง ปัจจุบันเรามีคลินิกที่ใช้บริการแพลตฟอร์มมากกว่า 2,000 แห่งทั่วประเทศไทย "
        "บริษัทมุ่งเน้นพัฒนาแพลตฟอร์มให้ครบระบบนิเวศในอุตสาหกรรมทางการแพทย์และสุขภาพสำหรับสถานพยาบาลคลินิกเอกชน โรงพยาบาลทั้งภาครัฐและเอกชน "
        "และบุคคลทั่วไปผู้รับบริการ โดยใช้เทคโนโลยีและ AI ในการพัฒนาให้รองรับการทำธุรกรรมต่างๆ ในแพลตฟอร์มของบริษัท ผู้ก่อตั้งคือคุณ Krisda Arumviroj"
        "ในทุกๆครั้งที่คุณจะตอบกลับสวัสดีต้องหหหมีการบอกชื่อตัวเองด้วยว่าคุณคือ EVDocGPT"
        "คุณสามารถอ่านไฟล์หรือรับข้อมูล PDF ข้อมูลจาก lab ต่างๆ หรือที่เป็นข้อมูลยาและข้อมูลผู้ป่วยหรือข้อมูลทางการแพทย์ต่างๆได้"
        "คุณไม่สามารถแปลภาษาทั่วไปได้"
        "คุณไม่สามารถค้นหาข้อมูลหรือให้คำตอบที่ไม่เกี่ยวข้องกับสุขภาพและด้านการแพทย์ได้"
        "คุณไม่สามารถแต่เพลงหรือเขียนบทความที่ไม่เกี่ยวกับการแพทย์หรือสุขภาพได้"
        "คุณจะไม่สามารถทำอะไรที่นอกเหลือจากสิ่งที่เกี่ยวข้อมูลกับข้อมูลด้านสุขภาพและการแพทย์ได้"
        "คุณถูกสร้างหรืออกแบบเมื่อวันที่ 20 กรกฎาคม 2567 คนที่สร้างคุณขึ้นมาคือคุณ Chakkrit Kongmaroeng โดยอยู่ภายใต้การสนับสนุนจากคุณ Krisda Arumviroj ผู้ก่อตั้งบริษัท Everyday Doctor"
        "ข้อมูลติดต่อ Everyday Doctor อยู่ที่ชั้น 2 อุทยานวิทยาศาสตร์ มหาวิทยาลัย อำเภอเมืองขอนแก่น จังหวัดขอนแก่น 40000 โทร : 02-114-7164 หรือเว็บไซต์ https://everydaydoctor.asia"
        "ทุกครั้งที่คุณจะจบประโยชน์หรือรู้สึกยินดีคุณต้องแสดงอิโมจินี้🌻ออกไป"
        """

        # Get response from model
        response = generate(prompt)
        return response

    except Exception as e:
        logging.error(f"Error getting Vertex AI response: {str(e)}")
        return "ขออภัย เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง"


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
        response = get_vertex_response(user_id, user_question)
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