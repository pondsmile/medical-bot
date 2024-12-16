from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from google import genai
from google.genai import types
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import VertexAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from vertexai.language_models import TextEmbeddingModel
import pythainlp
from pythainlp.tokenize import word_tokenize
import base64
import logging
import os
import tempfile

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


class ThaiTextSplitter(RecursiveCharacterTextSplitter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def split_text(self, text: str) -> list[str]:
        """Split text using Thai-aware splitting"""
        # ใช้ pythainlp ในการแบ่งประโยค
        sentences = pythainlp.sent_tokenize(text)
        return super().split_text("\n".join(sentences))


class RAGSystem:
    def __init__(self):
        self.embedding_model = TextEmbeddingModel.from_pretrained("textembedding-gecko@001")
        self.embeddings = VertexAIEmbeddings(
            model_name="textembedding-gecko@001",
            project="lexical-period-444405-e3",
            location="us-central1"
        )
        self.vector_store = None
        # ปรับขนาด chunk ให้เหมาะกับภาษาไทย
        self.chunk_size = 500
        self.chunk_overlap = 100

    def load_pdfs_from_folder(self, folder_path: str):
        """Load all PDFs from specified folder with Thai support"""
        try:
            pdf_files = [f for f in os.listdir(folder_path) if f.endswith('.pdf')]

            all_texts = []
            for pdf_file in pdf_files:
                pdf_path = os.path.join(folder_path, pdf_file)
                logging.info(f"กำลังประมวลผลไฟล์ PDF: {pdf_path}")

                # Load PDF with UTF-8 encoding
                loader = PyPDFLoader(pdf_path)
                documents = loader.load()

                # ใช้ Thai-aware text splitter
                text_splitter = ThaiTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    length_function=len,
                )
                texts = text_splitter.split_documents(documents)
                all_texts.extend(texts)

            if all_texts:
                self.vector_store = Chroma.from_documents(
                    documents=all_texts,
                    embedding=self.embeddings
                )
                logging.info(f"ประมวลผลไฟล์ PDF สำเร็จ {len(pdf_files)} ไฟล์")
                return True
            else:
                logging.warning("ไม่พบเนื้อหาในไฟล์ PDF")
                return False

        except Exception as e:
            logging.error(f"เกิดข้อผิดพลาดในการโหลด PDF: {str(e)}")
            return False

    def get_relevant_context(self, query, k=3):
        """ค้นหาบริบทที่เกี่ยวข้องจากคำถาม"""
        if not self.vector_store:
            return ""

        try:
            # ใช้ word_tokenize สำหรับการแบ่งคำภาษาไทย
            tokens = word_tokenize(query, engine="newmm")
            processed_query = " ".join(tokens)

            docs = self.vector_store.similarity_search(processed_query, k=k)
            return "\n".join([doc.page_content for doc in docs])
        except Exception as e:
            logging.error(f"เกิดข้อผิดพลาดในการค้นหาบริบท: {str(e)}")
            return ""


# Initialize RAG system
rag_system = RAGSystem()


def initialize_rag():
    """Initialize RAG system at startup"""
    data_folder = os.path.join(os.path.dirname(__file__), 'data')
    success = rag_system.load_pdfs_from_folder(data_folder)
    if success:
        logging.info("RAG system initialized successfully")
    else:
        logging.error("Failed to initialize RAG system")
    return success


def generate(prompt: str, context: str = "") -> str:
    """Generate response using Vertex AI Gemini with context"""
    client = genai.Client(
        vertexai=True,
        project="lexical-period-444405-e3",
        location="us-central1"
    )

    model = "gemini-2.0-flash-exp"

    # Create enhanced prompt with context
    enhanced_prompt = f"""
    Context from medical knowledge base:
    {context}

    User Question: {prompt}

    Based on the above context and your medical knowledge, please provide a comprehensive answer.
    """

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
                contents=[enhanced_prompt],
                config=generate_content_config,
        ):
            if chunk.text:
                full_response += chunk.text
    except Exception as e:
        logging.error(f"Error in generate_content_stream: {str(e)}")
        return "ขออภัย เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง"

    return full_response


def get_vertex_response(user_id: str, question: str) -> str:
    """Get response from Vertex AI Gemini with RAG"""
    try:
        # Retrieve relevant context
        context = rag_system.get_relevant_context(question)

        # Build prompt
        prompt = f"""
        คำถาม: {question}

        "คุณคือผู้ช่วยตอบปัญหาสุขภาพ คุณมีชื่อว่า EVDocGPT และนี้คือชื่อของคุณ EVDocGPT ที่ถูกออกแบบมาเพื่อให้คำแนะนำและข้อมูลเกี่ยวกับปัญหาสุขภาพ "
        "รวมถึงการตอบคำถามเกี่ยวกับโรคและสถานการณ์ทางการแพทย์ที่มีอยู่ในปัจจุบัน คุณประจำอยู่ที่บริษัท EverydayDoctor "
        "คุณสามารถให้คำวินิจฉัยโรคหรืออาการทางการแพทย์ได้เบื้องต้น"
        "คุณสามารถให้คำแนะนำเรื่องเพศได้ตามแหล่งอ้างอิงที่คุณมี"
        "คุณสามารถแนะนำเรื่องเพศศึกษาได้และให้คำตอบจากคำแนะนำของหมอจากแหล่งที่มาที่คุณมีมาอ้างอิงได้"
        "ซึ่งเป็นองค์กรที่มุ่งเน้นการให้ความรู้และการดูแลด้านสุขภาพให้กับผู้ใช้บริการ ด้วยฐานข้อมูลที่ครอบคลุมและการวิเคราะห์ที่แม่นยำ "
        """

        # Get response with context
        response = generate(prompt, context)
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


# Initialize and run app
if __name__ == "__main__":
    # Initialize RAG system before starting the app
    initialize_rag()
    app.run(host='0.0.0.0', port=8080)