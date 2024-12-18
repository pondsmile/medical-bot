import json
import requests


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


def main():
    print("พิมพ์ 'exit' เพื่อออกจากโปรแกรม")
    while True:
        user_input = input("คุณ: ")
        if user_input.lower() == 'exit':
            break

        response = query_agent(user_input)
        print(f"บอท: {response}")


if __name__ == "__main__":
    main()