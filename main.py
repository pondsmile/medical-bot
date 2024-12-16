from flask import Flask, request, abort
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    PushMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
import os
import PyPDF2
import re
from google import genai
from google.genai import types
import logging
import json
import vertexai

# ตั้งค่า logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# LINE Credentials
LINE_CHANNEL_SECRET = '5c8d2c4b41d6307b5df9f14ca01bb1df'
LINE_CHANNEL_ACCESS_TOKEN = 'S57WX85ldXlMWLDXqYMgwAFRFVsQ9PYjIzp5Ov8d1YV+U6yHvClLTqDAsUx2XZ8zMJdNlyztCGX+Qd+r9Hjaw4wYliM3cU4er6H57nlhIhE1mwSYDobeic8pk3igOO1JWhy/3TJd7iu9icbEeWrsdQdB04t89/1O/w1cDnyilFU='

# Initialize Vertex AI
vertexai.init(project="lexical-period-444405-e3", location="us-central1")


class PDFContentManager:
    def __init__(self, pdf_folder="data"):
        self.pdf_folder = pdf_folder
        self.document_categories = {}
        self.content_sections = []
        self.load_or_create_content()

    def categorize_document(self, text, filename):
        text_lower = text.lower()
        categories = []

        if any(word in text_lower for word in ['ค่ารักษา', 'ราคา', 'ค่าบริการ', 'อัตรา']):
            categories.append('pricing')
        if any(word in text_lower for word in ['โรค', 'อาการ', 'การรักษา', 'วินิจฉัย']):
            categories.append('medical')
        if any(word in text_lower for word in ['ขั้นตอน', 'วิธี', 'กระบวนการ']):
            categories.append('procedure')
        if any(word in text_lower for word in ['นโยบาย', 'ระเบียบ', 'ข้อบังคับ']):
            categories.append('policy')

        if not categories:
            categories.append('general')

        return categories

    def extract_section_metadata(self, section):
        metadata = {
            'type': 'unknown',
            'keywords': set(),
            'numbers': [],
            'has_pricing': False
        }

        text_lower = section.lower()

        if any(word in text_lower for word in ['บาท', 'ราคา', 'ค่า']):
            metadata['type'] = 'pricing'
            metadata['has_pricing'] = True
        elif any(word in text_lower for word in ['ขั้นตอน', 'วิธี']):
            metadata['type'] = 'procedure'
        elif any(word in text_lower for word in ['โรค', 'อาการ']):
            metadata['type'] = 'medical'

        important_words = [word for word in text_lower.split()
                           if len(word) > 3 and not word.isdigit()]
        metadata['keywords'] = set(important_words[:10])

        numbers = re.findall(r'\d+(?:,\d+)*(?:\.\d+)?', section)
        metadata['numbers'] = [float(num.replace(',', '')) for num in numbers]

        return metadata

    def split_into_logical_sections(self, text):
        sections = []
        current_section = ""

        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue

            if (re.match(r'^\d+\.', line) or
                    re.match(r'^[ก-ฮ]\.', line) or
                    line.isupper() or
                    any(line.startswith(prefix) for prefix in ['เรื่อง', 'บทที่', 'ส่วนที่'])):

                if current_section:
                    sections.append(current_section)
                current_section = line
            else:
                current_section += "\n" + line

        if current_section:
            sections.append(current_section)

        return sections

    def process_pdf_content(self):
        self.content_sections = []
        self.document_categories = {}

        for filename in os.listdir(self.pdf_folder):
            if filename.endswith('.pdf'):
                try:
                    file_path = os.path.join(self.pdf_folder, filename)
                    with open(file_path, 'rb') as file:
                        reader = PyPDF2.PdfReader(file)
                        full_text = ""

                        for page in reader.pages:
                            full_text += page.extract_text() + "\n"

                        categories = self.categorize_document(full_text, filename)
                        self.document_categories[filename] = categories

                        sections = self.split_into_logical_sections(full_text)

                        for section in sections:
                            if len(section.strip()) > 10:
                                metadata = self.extract_section_metadata(section)
                                self.content_sections.append({
                                    'content': section.strip(),
                                    'source': filename,
                                    'categories': categories,
                                    'metadata': metadata
                                })

                        logging.info(f"ประมวลผลไฟล์ {filename} สำเร็จ (ประเภท: {categories})")

                except Exception as e:
                    logging.error(f"เกิดข้อผิดพลาดในการประมวลผลไฟล์ {filename}: {e}")

    def find_relevant_content(self, query, max_sections=3):
        query_lower = query.lower()
        scored_sections = []

        query_words = set(query_lower.split())

        for section in self.content_sections:
            score = 0
            content_lower = section['content'].lower()
            metadata = section['metadata']

            matching_keywords = query_words.intersection(metadata['keywords'])
            score += len(matching_keywords) * 2

            for word in query_words:
                if len(word) > 3 and word in content_lower:
                    score += 1

            if ('ราคา' in query_lower or 'ค่า' in query_lower) and metadata['has_pricing']:
                score += 3

            if score > 0:
                scored_sections.append((score, section))

        scored_sections.sort(key=lambda x: x[0], reverse=True)
        return [section for score, section in scored_sections[:max_sections]]

    def create_response_context(self, query, relevant_sections):
        context_parts = []
        for section in relevant_sections:
            source = section['source']
            categories = ', '.join(section['categories'])
            context_parts.append(f"ข้อมูลจาก {source} (ประเภท: {categories}):\n{section['content']}")

        context = "\n\n".join(context_parts)

        prompt = f"""คุณเป็น AI ที่ถูกจำกัดให้ตอบเฉพาะข้อมูลที่มีในเอกสารอ้างอิงเท่านั้น

        คำถาม: {query}

        ข้อมูลอ้างอิง:
        {context}

        กฎในการตอบ:
        1. ตอบเฉพาะข้อมูลที่มีในเอกสารอ้างอิงข้างต้นเท่านั้น
        2. ห้ามเพิ่มเติมหรือสันนิษฐานข้อมูลนอกเหนือจากเอกสาร
        3. ถ้าไม่มีข้อมูลในเอกสาร ให้ตอบว่า "ขออภัย ไม่พบข้อมูลที่เกี่ยวข้องในเอกสาร"
        4. อ้างอิงที่มาของข้อมูลเสมอ
        5. ถ้าเป็นข้อมูลราคา ให้แสดงรายละเอียดทั้งหมดที่มี
        6. ลงท้ายด้วย 🌻

        คำตอบ:"""

        return prompt

    def save_content(self):
        os.makedirs("knowledge_base", exist_ok=True)
        data = {
            'categories': self.document_categories,
            'sections': [{
                'content': section['content'],
                'source': section['source'],
                'categories': section['categories'],
                'metadata': {
                    'type': section['metadata']['type'],
                    'has_pricing': section['metadata']['has_pricing'],
                    'numbers': section['metadata']['numbers']
                }
            } for section in self.content_sections]
        }
        with open("knowledge_base/processed_content.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info("บันทึกข้อมูลที่ประมวลผลแล้วสำเร็จ")

    def load_or_create_content(self):
        try:
            with open("knowledge_base/processed_content.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                self.document_categories = data['categories']
                self.content_sections = data['sections']
                for section in self.content_sections:
                    section['metadata']['keywords'] = set()  # Initialize empty set for keywords
            logging.info("โหลดข้อมูลที่ประมวลผลแล้วสำเร็จ")
        except:
            logging.info("ไม่พบข้อมูลที่ประมวลผลแล้ว กำลังประมวลผลใหม่...")
            self.process_pdf_content()
            self.save_content()

    def update_content(self):
        self.process_pdf_content()
        self.save_content()
        return "อัพเดทข้อมูลจากไฟล์ PDF เรียบร้อยแล้ว 🌻"


import logging
import vertexai
from vertexai.language_models import TextGenerationModel


class VertexAIHandler:
    def __init__(self):
        try:
            # Initialize Vertex AI
            vertexai.init(
                project="lexical-period-444405-e3",
                location="us-central1"
            )

            # Initialize the text model
            self.model = TextGenerationModel.from_pretrained("text-bison@002")
            logging.info("VertexAI Handler initialized successfully")

        except Exception as e:
            logging.error(f"Failed to initialize VertexAI Handler: {e}")
            raise

    def generate_response(self, prompt):
        try:
            response = self.model.predict(
                prompt,
                temperature=0.3,
                max_output_tokens=8192,
                top_k=40,
                top_p=0.8,
            )
            return response.text
        except Exception as e:
            logging.error(f"Error generating response: {e}")
            return "ขออภัย เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง 🌻"


# Initialize Flask and LINE
app = Flask(__name__)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)

# Initialize Content Manager and Vertex AI Handler
content_manager = PDFContentManager()
vertex_handler = VertexAIHandler()


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

        if user_question.strip().lower() == "เรียนรู้ข้อมูลจาก pdf ใหม่หน่อย":
            response = content_manager.update_content()
        else:
            relevant_sections = content_manager.find_relevant_content(user_question)
            if not relevant_sections:
                response = "ขออภัย ไม่พบข้อมูลที่เกี่ยวข้องในเอกสาร 🌻"
            else:
                prompt = content_manager.create_response_context(user_question, relevant_sections)
                response = vertex_handler.generate_response(prompt)

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
    app.run(host='0.0.0.0', port=8080)