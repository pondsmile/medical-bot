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
                        "ทุกครั้งที่คุณจะจบประโยชน์หรือรู้สึกยินดีคุณต้องแสดงอิโมจินี้🌻ออกไป"
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