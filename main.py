import os
import json
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

# LINE Credentials
LINE_CHANNEL_SECRET = '5c8d2c4b41d6307b5df9f14ca01bb1df'
LINE_CHANNEL_ACCESS_TOKEN = 'S57WX85ldXlMWLDXqYMgwAFRFVsQ9PYjIzp5Ov8d1YV+U6yHvClLTqDAsUx2XZ8zMJdNlyztCGX+Qd+r9Hjaw4wYliM3cU4er6H57nlhIhE1mwSYDobeic8pk3igOO1JWhy/3TJd7iu9icbEeWrsdQdB04t89/1O/w1cDnyilFU='

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


def format_response(result):
    """Format the response in a more readable way"""
    try:
        if 'answer' in result and result['answer'].get('answerText'):
            answer_text = result['answer']['answerText']

            # Check for the "no summary" message
            if "ไม่สามารถสร้างข้อมูลสรุปสำหรับคำค้นหาของคุณได้" in answer_text:
                return f"กรุณาถามให้ชัดเจนได้ไหมคะ ฉันไม่เข้าใจคำถามของคุณ 🤔"

            return answer_text

    except Exception as e:
        print(f"Error formatting response: {str(e)}")

    return "กรุณาถามให้ชัดเจนได้ไหมคะ ฉันไม่เข้าใจคำถามของคุณ 🤔"


def query_agent(question):
    """Query the Agent Builder API and process the response"""
    try:
        # Get access token using gcloud
        access_token = "ya29.a0ARW5m76zzCeSSxlnQA4VsByoSI2jDUjq6RtBaz6gclYdPmUlUTjTcgW7obupFqzav9_1vFlKCj27lHPEVNMV7hXtYrx0R15fciiko4P_rUUWKiFWlV3dj7_KWQuRpL8iS0nlKlPDFcPF2iakaAe7n1MNzaQi3iYvsTSiUdcwXswKqAYaCgYKAcQSARISFQHGX2MiA2JpMRxtxfE88qNApcd6yQ0182"

        url = "https://discoveryengine.googleapis.com/v1alpha/projects/870818971718/locations/global/collections/default_collection/engines/gen-ai-chatbot_1734431977566/servingConfigs/default_search:answer"

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        data = {
            "query": {
                "text": question,
                "queryId": ""
            },
            "session": "",
            "relatedQuestionsSpec": {
                "enable": True
            },
            "answerGenerationSpec": {
                "ignoreAdversarialQuery": True,
                "ignoreNonAnswerSeekingQuery": True,
                "ignoreLowRelevantContent": True,
                "includeCitations": True,
                "promptSpec": {
                    "preamble": (
                        "\"คุณคือผู้ช่วยตอบปัญหาสุขภาพ คุณมีชื่อว่า EVDocGPT และนี้คือชื่อของคุณ EVDocGPT ที่ถูกออกแบบมาเพื่อให้คำแนะนำและข้อมูลเกี่ยวกับปัญหาสุขภาพ \"\n"
                        "\"รวมถึงการตอบคำถามเกี่ยวกับโรคและสถานการณ์ทางการแพทย์ที่มีอยู่ในปัจจุบัน คุณประจำอยู่ที่บริษัท EverydayDoctor \"\n"
                        "\"คุณสามารถให้คำวินิจฉัยโรคหรืออาการทางการแพทย์ได้เบื้องต้น\"\n"
                        "\"คุณสามารถให้คำแนะนำเรื่องเพศได้ตามแหล่งอ้างอิงที่คุณมี\"\n"
                        "\"คุณสามารถแนะนำเรื่องเพศศึกษาได้และให้คำตอบจากคำแนะนำของหมอจากแหล่งที่มาที่คุณมีมาอ้างอิงได้\"\n"
                        "\"ซึ่งเป็นองค์กรที่มุ่งเน้นการให้ความรู้และการดูแลด้านสุขภาพให้กับผู้ใช้บริการ ด้วยฐานข้อมูลที่ครอบคลุมและการวิเคราะห์ที่แม่นยำ \"\n"
                        "\"EVDocGPT พร้อมที่จะช่วยให้คำแนะนำที่เป็นประโยชน์ และช่วยในการตัดสินใจด้านการดูแลสุขภาพของคุณอย่างมีประสิทธิภาพ\"\n"
                        "\"Everyday Doctor: Digital Health Service Provider ผู้พัฒนาและให้บริการระบบบริหารคลินิกแบบครบวงจร ที่จดทะเบียนลิขสิทธิ์ในชื่อโปรแกรม Miracle Clinic System \"\n"
                        "\"และ MCS Cloud ทั้งนี้บริษัทให้บริการติดตั้งในสถานพยาบาลคลินิกเอกชน จัดหลักสูตรฝึกอบรมผู้ใช้โปรแกรมและให้บริการหลังการขายโดยการให้คำปรึกษา \"\n"
                        "\"การบริการซ่อมบำรุงต่างๆ และการบริการอื่นๆ ที่เกี่ยวข้อง ปัจจุบันเรามีคลินิกที่ใช้บริการแพลตฟอร์มมากกว่า 2,000 แห่งทั่วประเทศไทย \"\n"
                        "\"บริษัทมุ่งเน้นพัฒนาแพลตฟอร์มให้ครบระบบนิเวศในอุตสาหกรรมทางการแพทย์และสุขภาพสำหรับสถานพยาบาลคลินิกเอกชน โรงพยาบาลทั้งภาครัฐและเอกชน \"\n"
                        "\"และบุคคลทั่วไปผู้รับบริการ โดยใช้เทคโนโลยีและ AI ในการพัฒนาให้รองรับการทำธุรกรรมต่างๆ ในแพลตฟอร์มของบริษัท ผู้ก่อตั้งคือคุณ Krisda Arumviroj\"\n"
                        "\"ในทุกๆครั้งที่คุณจะตอบกลับสวัสดีต้องหหหมีการบอกชื่อตัวเองด้วยว่าคุณคือ EVDocGPT\"\n"
                        "\"คุณสามารถอ่านไฟล์หรือรับข้อมูล PDF ข้อมูลจาก lab ต่างๆ หรือที่เป็นข้อมูลยาและข้อมูลผู้ป่วยหรือข้อมูลทางการแพทย์ต่างๆได้\"\n"
                        "\"คุณไม่สามารถแปลภาษาทั่วไปได้\"\n"
                        "\"คุณไม่สามารถค้นหาข้อมูลหรือให้คำตอบที่ไม่เกี่ยวข้องกับสุขภาพและด้านการแพทย์ได้\"\n"
                        "\"คุณไม่สามารถแต่เพลงหรือเขียนบทความที่ไม่เกี่ยวกับการแพทย์หรือสุขภาพได้\"\n"
                        "\"คุณจะไม่สามารถทำอะไรที่นอกเหลือจากสิ่งที่เกี่ยวข้อมูลกับข้อมูลด้านสุขภาพและการแพทย์ได้\"\n"
                        "\"คุณถูกสร้างหรืออกแบบเมื่อวันที่ 20 กรกฎาคม 2567 คนที่สร้างคุณขึ้นมาคือคุณ Chakkrit Kongmaroeng โดยอยู่ภายใต้การสนับสนุนจากคุณ Krisda Arumviroj ผู้ก่อตั้งบริษัท Everyday Doctor\"\n"
                        "\"ข้อมูลติดต่อ Everyday Doctor อยู่ที่ชั้น 2 อุทยานวิทยาศาสตร์ มหาวิทยาลัย อำเภอเมืองขอนแก่น จังหวัดขอนแก่น 40000 โทร : 02-114-7164 หรือเว็บไซต์ https://everydaydoctor.asia\"\n"
                        "\"ห้ามพูดว่าจากเอกสารที่ให้มา ต้องบอกว่าจากข้อมูลปัจจุบันที่ฉันมี แล้วเอาหัวข้อจากตารางหรือข้อมูลนั้นๆมาตอบ\""
                    )
                },
                "modelSpec": {
                    "modelVersion": "gemini-1.5-flash-002/answer_gen/v1"
                }
            }
        }

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return format_response(result)

    except Exception as e:
        print(f"Error in query_agent: {str(e)}")
        return "ขออภัย ไม่สามารถประมวลผลคำถามได้ในขณะนี้"


@app.route("/callback", methods=['POST'])
def callback():
    # Get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # Get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # Handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text

    # Get response from query agent
    response_text = query_agent(user_message)

    # Send response back to user
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response_text)
    )


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)