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
import logging
import json
import vertexai
from vertexai.language_models import TextGenerationModel

# ตั้งค่า logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# LINE Credentials
LINE_CHANNEL_SECRET = '5c8d2c4b41d6307b5df9f14ca01bb1df'
LINE_CHANNEL_ACCESS_TOKEN = 'S57WX85ldXlMWLDXqYMgwAFRFVsQ9PYjIzp5Ov8d1YV+U6yHvClLTqDAsUx2XZ8zMJdNlyztCGX+Qd+r9Hjaw4wYliM3cU4er6H57nlhIhE1mwSYDobeic8pk3igOO1JWhy/3TJd7iu9icbEeWrsdQdB04t89/1O/w1cDnyilFU='

# Initialize Vertex AI
vertexai.init(project="lexical-period-444405-e3", location="us-central1")

# เพิ่ม VertexAIHandler class
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

class PDFProcessor:
    def __init__(self, pdf_folder="data"):
        self.pdf_folder = pdf_folder
        self.doc_buffer = []

    def _clean_text(self, text):
        """ทำความสะอาดข้อความ"""
        text = re.sub(r'\s+', ' ', text)  # แทนที่ whitespace หลายตัวด้วยช่องว่างเดียว
        text = text.strip()
        return text

    def _extract_prices(self, text):
        """แยกราคาจากข้อความ"""
        prices = re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?(?:\s*-\s*\d+(?:,\d{3})*(?:\.\d+)?)?(?=\s*บาท)', text)
        return [p.replace(',', '') for p in prices]

    def _identify_content_type(self, text):
        """ระบุประเภทของเนื้อหา"""
        text_lower = text.lower()
        categories = []

        # ตรวจสอบหมวดหมู่
        if any(word in text_lower for word in ['ราคา', 'บาท', 'ค่า']):
            categories.append('pricing')
        if any(word in text_lower for word in ['ขั้นตอน', 'วิธี', 'กระบวนการ']):
            categories.append('procedure')
        if any(word in text_lower for word in ['รักษา', 'การรักษา']):
            categories.append('treatment')
        if any(word in text_lower for word in ['อาการ', 'โรค']):
            categories.append('symptom')

        if not categories:
            categories.append('general')

        return categories

    def _extract_section_metadata(self, text):
        """ดึงข้อมูล metadata จากส่วนเนื้อหา"""
        return {
            'categories': self._identify_content_type(text),
            'prices': self._extract_prices(text),
            'word_count': len(text.split()),
            'has_table': bool(re.search(r'\|\s*\w+\s*\|', text))
        }

    def process_pdf_content(self):
        """ประมวลผลเนื้อหาจากไฟล์ PDF ทั้งหมด"""
        documents = []

        for filename in os.listdir(self.pdf_folder):
            if filename.endswith('.pdf'):
                file_path = os.path.join(self.pdf_folder, filename)
                try:
                    with open(file_path, 'rb') as file:
                        reader = PyPDF2.PdfReader(file)
                        text = ""

                        # รวมเนื้อหาทั้งหมดจากทุกหน้า
                        for page in reader.pages:
                            text += page.extract_text() + "\n"

                        # แบ่งเนื้อหาเป็นส่วนๆ
                        sections = self._split_into_sections(text)

                        # เพิ่ม metadata และเก็บข้อมูล
                        for section in sections:
                            clean_text = self._clean_text(section)
                            if len(clean_text) > 50:  # ข้ามส่วนที่สั้นเกินไป
                                metadata = self._extract_section_metadata(clean_text)
                                documents.append({
                                    'content': clean_text,
                                    'source': filename,
                                    'metadata': metadata
                                })

                        logging.info(f"ประมวลผลไฟล์ {filename} สำเร็จ")

                except Exception as e:
                    logging.error(f"เกิดข้อผิดพลาดในการประมวลผลไฟล์ {filename}: {e}")

        return documents

    def _split_into_sections(self, text):
        """แบ่งเนื้อหาเป็นส่วนๆ ตามโครงสร้าง"""
        sections = []
        current_section = ""

        for line in text.split('\n'):
            if self._is_new_section(line):
                if current_section.strip():
                    sections.append(current_section.strip())
                current_section = line
            else:
                current_section += "\n" + line

        if current_section.strip():
            sections.append(current_section.strip())

        return sections

    def _is_new_section(self, line):
        """ตรวจสอบว่าเป็นหัวข้อใหม่หรือไม่"""
        patterns = [
            r'^\d+\.[\d\.]*\s+\w+',  # เช่น "1.", "1.1.", "1.1.1."
            r'^[ก-ฮ]\.\s+\w+',  # เช่น "ก."
            r'^[A-Z][A-Za-z\s]+:',  # เช่น "Section:"
            r'^[\u0E01-\u0E5B]+:',  # หัวข้อภาษาไทยตามด้วย ":"
        ]
        return any(re.match(pattern, line.strip()) for pattern in patterns)


class SemanticSearch:
    def __init__(self):
        self.vertex_handler = VertexAIHandler()
        self.documents = []

    def update_documents(self, documents):
        """อัพเดทฐานข้อมูลเอกสาร"""
        self.documents = documents

    def search(self, query, top_k=3):
        """ค้นหาเนื้อหาที่เกี่ยวข้องที่สุด"""
        try:
            # สร้าง prompt สำหรับการค้นหา
            search_prompt = f"""
            กรุณาวิเคราะห์และเลือกเนื้อหาที่เกี่ยวข้องที่สุดกับคำถามต่อไปนี้:

            คำถาม: {query}

            เนื้อหาที่มี:
            {self._format_documents()}

            โปรดเลือกและส่งคืนเฉพาะส่วนที่เกี่ยวข้องโดยตรง โดยคงไว้ซึ่งแหล่งที่มาของข้อมูล (ชื่อไฟล์)
            ตอบในรูปแบบ:
            [ชื่อไฟล์]
            เนื้อหาที่เกี่ยวข้อง
            """

            response = self.vertex_handler.generate_response(search_prompt)

            return self._parse_search_response(response)

        except Exception as e:
            logging.error(f"เกิดข้อผิดพลาดในการค้นหา: {e}")
            return []

    def _format_documents(self):
        """จัดรูปแบบเอกสารสำหรับการค้นหา"""
        formatted_docs = []
        for doc in self.documents:
            categories = ', '.join(doc['metadata']['categories'])
            formatted_docs.append(
                f"[{doc['source']} | {categories}]\n{doc['content']}"
            )
        return "\n\n".join(formatted_docs)

    def _parse_search_response(self, response):
        """แยกผลลัพธ์การค้นหา"""
        sections = []
        current_section = {'source': None, 'content': ''}

        for line in response.split('\n'):
            if line.strip():
                if line.startswith('[') and ']' in line:
                    if current_section['source']:
                        sections.append(current_section)
                    source = line[1:line.index(']')]
                    current_section = {
                        'source': source,
                        'content': line[line.index(']') + 1:].strip()
                    }
                else:
                    current_section['content'] += '\n' + line.strip()

        if current_section['source']:
            sections.append(current_section)

        return sections


class ResponseGenerator:
    def __init__(self):
        self.vertex_handler = VertexAIHandler()

    def generate(self, query: str, relevant_sections: list) -> str:
        """สร้างคำตอบจากข้อมูลที่เกี่ยวข้อง"""
        if not relevant_sections:
            return "ขออภัย ไม่พบข้อมูลที่เกี่ยวข้องในเอกสาร 🌻"

        # สร้าง context จากส่วนที่เกี่ยวข้อง
        context = "\n\n".join([
            f"จาก {section['source']}:\n{section['content']}"
            for section in relevant_sections
        ])

        prompt = f"""คุณคือ EVDocGPT ผู้ช่วยตอบคำถามด้านการแพทย์และทันตกรรม

        คำถาม: {query}

        ข้อมูลอ้างอิง:
        {context}

        กรุณาตอบโดย:
        1. ใช้เฉพาะข้อมูลจากเอกสารอ้างอิงเท่านั้น
        2. ถ้าเป็นข้อมูลราคา ให้แสดงรายละเอียดทั้งหมดที่มี
        3. อ้างอิงที่มาของข้อมูลเสมอ
        4. ตอบให้กระชับและตรงประเด็น
        5. ถ้าไม่มีข้อมูลในเอกสาร ให้แจ้งว่าไม่พบข้อมูล
        6. ลงท้ายด้วย 🌻"""

        try:
            response = self.vertex_handler.generate_response(prompt)
            return response
        except Exception as e:
            logging.error(f"เกิดข้อผิดพลาดในการสร้างคำตอบ: {e}")
            return "ขออภัย เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง 🌻"


class RAGSystem:
    def __init__(self, pdf_folder="data"):
        self.pdf_processor = PDFProcessor(pdf_folder)
        self.semantic_search = SemanticSearch()
        self.response_generator = ResponseGenerator()
        self.load_or_create_knowledge_base()

    def load_or_create_knowledge_base(self):
        """โหลดหรือสร้างฐานความรู้ใหม่"""
        try:
            with open("knowledge_base/documents.json", "r", encoding="utf-8") as f:
                documents = json.load(f)
                self.semantic_search.update_documents(documents)
                logging.info("โหลดฐานความรู้ที่มีอยู่สำเร็จ")
        except:
            logging.info("ไม่พบฐานความรู้เดิม กำลังสร้างใหม่...")
            self.update_knowledge_base()

    def update_knowledge_base(self):
        """อัพเดทฐานความรู้"""
        try:
            documents = self.pdf_processor.process_pdf_content()
            self.semantic_search.update_documents(documents)

            os.makedirs("knowledge_base", exist_ok=True)
            with open("knowledge_base/documents.json", "w", encoding="utf-8") as f:
                json.dump(documents, f, ensure_ascii=False, indent=2)

            logging.info("อัพเดทฐานความรู้สำเร็จ")
            return "เรียนรู้ข้อมูลจากไฟล์ PDF ใหม่เรียบร้อยแล้ว 🌻"
        except Exception as e:
            logging.error(f"เกิดข้อผิดพลาดในการอัพเดทฐานความรู้: {e}")
            return "เกิดข้อผิดพลาดในการอัพเดทฐานความรู้ กรุณาลองใหม่อีกครั้ง 🌻"

    def get_response(self, query: str) -> str:
        """ค้นหาและสร้างคำตอบ"""
        try:
            # ค้นหาเนื้อหาที่เกี่ยวข้อง
            relevant_sections = self.semantic_search.search(query)

            # สร้างคำตอบ
            response = self.response_generator.generate(query, relevant_sections)
            return response
        except Exception as e:
            logging.error(f"เกิดข้อผิดพลาดในการสร้างคำตอบ: {e}")
            return "ขออภัย เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง 🌻"


# Initialize Flask and LINE
app = Flask(__name__)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)

# Initialize RAG System
rag_system = RAGSystem()


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
                messages=[TextMessage(text="กรุณารอสักครู่ กำลังค้นหาข้อมูล...")]
            )
        )

        # ตรวจสอบคำสั่งพิเศษ
        if user_question.strip().lower() == "เรียนรู้ข้อมูลจาก pdf ใหม่หน่อย":
            response = rag_system.update_knowledge_base()
        else:
            # ค้นหาและสร้างคำตอบ
            response = rag_system.get_response(user_question)

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
    # Make sure the knowledge_base directory exists
    os.makedirs("knowledge_base", exist_ok=True)

    # Run the Flask app
    app.run(host='0.0.0.0', port=8080)