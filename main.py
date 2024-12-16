from flask import Flask, request, abort
# LINE SDK v3 imports
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from google import genai
from google.genai import types
import logging
import os
import vertexai

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

# Initialize LINE Bot with v3
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)

# Initialize Vertex AI
import vertexai

vertexai.init(
    project="lexical-period-444405-e3",
    location="us-central1"
)


def load_pdf_content():
    pdf_content = """
    ตารางบัญชีอัตราค่ารักษาพยาบาล คณะทันตแพทยศาสตร์มหาวิทยาลัยขอนแก่น พ.ศ. 2567

    1. งานทันตกรรมบูรณะ
    1.1 อุดชั่วคราว
    - บัตรทอง: 200 บาท
    - กรมบัญชีกลาง: 240 บาท
    - นักศึกษาปริญญาตรี: 100-240 บาท
    - นักศึกษาหลังปริญญา: 240-300 บาท
    - อาจารย์/ทันตแพทย์: 240-400 บาท

    1.2 อุดฟันด้วยอมัลกัม
    - ด้านเดียว: 150-500 บาท
    - สองด้าน: 200-700 บาท
    - สามด้านขึ้นไป: 250-1,000 บาท
    กรณีรองพื้นด้วย GI คิดเพิ่ม 50-100 บาท
    ถ้าอุดพร้อมหมุด (Amalgam pin) คิดเพิ่มตัวละ 200 บาท
    กรณีที่ต้องใช้ Amalgam bonding เพิ่มอีก 200 บาท

    1.3 อุดฟันด้วยคอมโพสิตเรซินหรือกลาสไอโอโนเมอร์
    - ด้านเดียว: 200-700 บาท (ค่าวัสดุ 50 บาท)
    - สองด้าน: 300-1,000 บาท (ค่าวัสดุ 50 บาท)
    - สามด้านขึ้นไป: 400-1,300 บาท (ค่าวัสดุ 50 บาท)

    2. งานทันตกรรมประดิษฐ์
    2.1 ฟันเทียมทั้งปาก
    - ฟันเทียมทั้งปากฐานอะคริลิก: 2,000-18,000 บาท
    - ฟันเทียมทั้งปากบนหรือล่างฐานอะคริลิก: 1,250-9,000 บาท
    - ฟันเทียมทั้งปากบนหรือล่างฐานโลหะ: 2,200-9,000 บาท

    3. งานศัลยกรรมช่องปาก
    3.1 ถอนฟันหรือรากฟันโดย Closed method
    - ฟันที่เป็นโรคปริทันต์ที่โยก: 200-600 บาท
    - ถอนฟันถาวรหรือรากฟัน: 200-1,000 บาท
    - ถอนฟันถาวรอย่างยาก: 350-1,500 บาท

    3.2 ผ่าตัดฟันคุด ฟันฝัง
    - Soft Tissue Impaction: 350-1,500 บาท
    - Bony Impaction (depth A): 700-3,500 บาท (ค่าวัสดุ 100 บาท)
    - Complete bony impaction (depth B or C): 800-7,000 บาท (ค่าวัสดุ 100 บาท)

    4. งานทันตกรรมจัดฟัน
    4.1 Metal Bracket System (แบบโลหะ)
    - ค่ารักษาทั้งปาก: 20,000-70,000 บาท
    - แบ่งชำระเป็นงวด งวดแรก: 5,000 บาท
    - งวดต่อไป: 500-2,000 บาท/ครั้ง
    - กรณี Bracket หลุดต้องติดใหม่: 300-600 บาท/ตัว

    5. งานทันตรังสี
    5.1 Cephalometry ดิจิทัล: 350-400 บาท/แผ่น
    5.2 Dental ดิจิทัล: 120-150 บาท/แผ่น
    5.3 Panoramic ดิจิทัล: 350-400 บาท/แผ่น
    5.4 CT Facial bone SKULL: 3,500-6,000 บาท
    """
    return pdf_content


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
    try:
        # ดึงข้อมูลจาก PDF
        pdf_content = load_pdf_content()

        # สร้าง prompt ที่เน้นการค้นหาข้อมูลจาก PDF ก่อน
        prompt = f"""
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
        "คุณถูกสร้างหรืออกแบบเมื่อวันที่ 20 กรกฎาคม 2567 คนที่สร้างคุณขึ้นมาคือคุณ Krisda Arumviroj ผู้ก่อตั้งบริษัท Everyday Doctor"
        "ข้อมูลติดต่อ Everyday Doctor อยู่ที่ชั้น 2 อุทยานวิทยาศาสตร์ มหาวิทยาลัย อำเภอเมืองขอนแก่น จังหวัดขอนแก่น 40000 โทร : 02-114-7164 หรือเว็บไซต์ https://everydaydoctor.asia"
        "ทุกครั้งที่คุณจะจบประโยชน์หรือรู้สึกยินดีคุณต้องแสดงอิโมจินี้🌻ออกไป"

        ข้อมูลที่มี:
        {pdf_content}

        คำถาม: {question}

        กรุณาตอบคำถามตามหลักเกณฑ์ต่อไปนี้:

        1. ค้นหาข้อมูลจากตารางค่ารักษาพยาบาลก่อนเป็นอันดับแรก
        2. ถ้าพบข้อมูลในตาราง:
           - ให้ตอบโดยอ้างอิงข้อมูลจากตารางโดยตรง
           - แสดงราคาแยกตามประเภทผู้ป่วย (ถ้ามี)
           - ระบุค่าใช้จ่ายเพิ่มเติม เช่น ค่าวัสดุ ค่าแล็บ (ถ้ามี)
           - ถ้าเป็นคำถามเกี่ยวกับราคาที่ถูกที่สุด ให้เปรียบเทียบและระบุตัวเลือกที่ถูกที่สุดพร้อมเงื่อนไข
        3. ถ้าไม่พบข้อมูลในตาราง:
           - ตอบว่า "ขออภัย ไม่พบข้อมูลที่ต้องการในตารางค่ารักษาพยาบาล" 
        4. ที่สุดท้ายของการตอบ ให้ลงท้ายด้วย 🌻

        ตัวอย่างการตอบเมื่อพบข้อมูล:
        "ค่าถอนฟันถาวรในตารางค่ารักษาพยาบาลมีดังนี้:
        - บัตรทอง: 200 บาท
        - กรมบัญชีกลาง: 240 บาท
        - นักศึกษาปริญญาตรี: 100-240 บาท
        - นักศึกษาหลังปริญญา: 240-300 บาท
        - อาจารย์/ทันตแพทย์: 240-400 บาท
        ราคาถูกที่สุดคือ 100 บาท สำหรับนักศึกษาปริญญาตรี 🌻"
        """

        # Get response from model
        response = generate(prompt)
        return response

    except Exception as e:
        logging.error(f"Error getting Vertex AI response: {str(e)}")
        return "ขออภัย เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง 🌻"


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_question = event.message.text
    logging.info(f"Received message from {user_id}: {user_question}")

    try:
        # ส่งข้อความรอก่อน
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="กรุณารอสักครู่ กำลังประมวลผล...")]
            )
        )

        # ประมวลผลคำตอบ
        response = get_vertex_response(user_id, user_question)
        logging.info(f"Generated response: {response}")

        # ส่งคำตอบกลับ
        line_bot_api.push_message_with_http_info(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=response)]
            )
        )

    except Exception as e:
        logging.error(f"Error handling message: {e}")
        line_bot_api.push_message_with_http_info(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text="ขออภัย เกิดข้อผิดพลาดในการประมวลผล 🌻")]
            )
        )


if __name__ == "__main__":
    # Initialize Vertex AI
    vertexai.init(project="lexical-period-444405-e3", location="us-central1")
    # Run app
    app.run(host='0.0.0.0', port=8080)