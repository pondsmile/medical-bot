from flask import Flask, request, abort
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.embeddings import VertexEmbeddings
from langchain.chat_models import ChatVertexAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
import logging
import os

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
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)


class RAGSystem:
    def __init__(self, project_id: str = "lexical-period-444405-e3", location: str = "us-central1"):
        """Initialize RAG system with Google Cloud settings"""
        self.project_id = project_id
        self.location = location

        # Initialize Vertex AI
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id

        # Initialize models
        self.embeddings = VertexEmbeddings(
            model_name="textembedding-gecko",
            project=project_id,
            location=location,
        )

        self.llm = ChatVertexAI(
            model_name="chat-bison",
            project=project_id,
            location=location,
            max_output_tokens=1024,
            temperature=0.1,
        )

        self.vectorstore = None
        self.chain = None

    def create_knowledge_base(self, pdf_path: str):
        """Create knowledge base from PDF document"""
        try:
            # Load PDF
            loader = PyPDFLoader(pdf_path)
            documents = loader.load()

            # Split into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=100,
                length_function=len,
            )
            splits = text_splitter.split_documents(documents)

            # Create vector store
            self.vectorstore = FAISS.from_documents(
                documents=splits,
                embedding=self.embeddings
            )

            # Save vector store
            self.vectorstore.save_local("knowledge_base")

            # Create retriever
            retriever = self.vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 3}
            )

            # Create prompt template
            template = """คุณคือผู้ช่วย EVDocGPT จากบริษัท Everyday Doctor
            กรุณาใช้ข้อมูลต่อไปนี้ในการตอบคำถาม:

            {context}

            คำถาม: {question}

            กรุณาตอบตามหลักเกณฑ์ต่อไปนี้:
            1. ตอบโดยอ้างอิงเฉพาะข้อมูลที่มีในเอกสาร
            2. ถ้าพบข้อมูล ให้ระบุรายละเอียดราคาและเงื่อนไขให้ครบถ้วน
            3. ถ้าไม่พบข้อมูล ให้แจ้งว่า "ขออภัย ไม่พบข้อมูลที่ต้องการในเอกสาร"
            4. จบคำตอบด้วย 🌻 เสมอ

            คำตอบ:"""

            PROMPT = PromptTemplate(
                template=template,
                input_variables=["context", "question"],
            )

            # Create chain
            self.chain = (
                    {"context": retriever, "question": RunnablePassthrough()}
                    | PROMPT
                    | self.llm
            )

            return True

        except Exception as e:
            logging.error(f"Error creating knowledge base: {str(e)}")
            return False

    def load_knowledge_base(self):
        """Load existing knowledge base"""
        try:
            self.vectorstore = FAISS.load_local("knowledge_base", self.embeddings)
            retriever = self.vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 3}
            )

            # Recreate prompt template and chain
            template = """คุณคือผู้ช่วย EVDocGPT จากบริษัท Everyday Doctor
            กรุณาใช้ข้อมูลต่อไปนี้ในการตอบคำถาม:

            {context}

            คำถาม: {question}

            กรุณาตอบตามหลักเกณฑ์ต่อไปนี้:
            1. ตอบโดยอ้างอิงเฉพาะข้อมูลที่มีในเอกสาร
            2. ถ้าพบข้อมูล ให้ระบุรายละเอียดราคาและเงื่อนไขให้ครบถ้วน
            3. ถ้าไม่พบข้อมูล ให้แจ้งว่า "ขออภัย ไม่พบข้อมูลที่ต้องการในเอกสาร"
            4. จบคำตอบด้วย 🌻 เสมอ

            คำตอบ:"""

            PROMPT = PromptTemplate(
                template=template,
                input_variables=["context", "question"],
            )

            self.chain = (
                    {"context": retriever, "question": RunnablePassthrough()}
                    | PROMPT
                    | self.llm
            )
            return True
        except Exception as e:
            logging.error(f"Error loading knowledge base: {str(e)}")
            return False

    def query(self, question: str) -> str:
        """Query the knowledge base"""
        try:
            if not self.chain:
                return "ระบบยังไม่พร้อมใช้งาน กรุณาสร้างหรือโหลด knowledge base ก่อน 🌻"

            response = self.chain.invoke(question)
            return response

        except Exception as e:
            logging.error(f"Error querying knowledge base: {str(e)}")
            return "ขออภัย เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง 🌻"


# Initialize RAG system
rag_system = RAGSystem(project_id="lexical-period-444405-e3")


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

        # ตรวจสอบว่ามี knowledge base หรือยัง
        if not rag_system.vectorstore:
            if not rag_system.load_knowledge_base():
                response = "ระบบยังไม่พร้อมใช้งาน กรุณาติดต่อผู้ดูแลระบบ 🌻"
            else:
                response = rag_system.query(user_question)
        else:
            response = rag_system.query(user_question)

        # ส่งคำตอบกลับ
        line_bot_api.push_message_with_http_info(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=response)]
            )
        )

    except Exception as e:
        logging.error(f"Error handling message: {str(e)}")
        line_bot_api.push_message_with_http_info(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text="ขออภัย เกิดข้อผิดพลาดในการประมวลผล 🌻")]
            )
        )


if __name__ == "__main__":
    # สร้าง knowledge base จาก PDF (ทำครั้งแรกหรือเมื่อต้องการอัพเดต)
    rag_system.create_knowledge_base("data/hospital_rates.pdf")

    # หรือโหลด knowledge base ที่มีอยู่แล้ว
    rag_system.load_knowledge_base()

    # Run app
    app.run(host='0.0.0.0', port=8080)