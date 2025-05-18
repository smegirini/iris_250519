import requests
import os
import json
from io import BytesIO
import PyPDF2
from iris import ChatContext
from iris.decorators import *

# ChatContext에 load_attachment 메소드 추가
def load_attachment(chat):
    """
    메시지의 첨부 파일 데이터를 가져오는 도우미 함수
    """
    try:
        if hasattr(chat.message, "attachment") and chat.message.attachment:
            try:
                # JSON 문자열이면 파싱 시도
                if isinstance(chat.message.attachment, str):
                    return json.loads(chat.message.attachment)
                return chat.message.attachment
            except Exception:
                return chat.message.attachment
        return None
    except Exception as e:
        print(f"첨부 파일 로드 오류: {str(e)}")
        return None

# Azure OpenAI API 설정
AZURE_OPENAI_ENDPOINT = "https://dwf.openai.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview"
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")

def summarize_pdf_with_gpt(pdf_content, prompt="이 PDF 문서의 내용을 핵심만 간략하게 요약해주세요."):
    """
    PDF 내용을 Azure OpenAI GPT-4.1 모델에 전달하여 요약 받기
    """
    try:
        headers = {
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_API_KEY
        }
        
        data = {
            "messages": [
                {
                    "role": "system", 
                    "content": "당신은 PDF 문서를 요약하는 도우미입니다. 주어진 텍스트를 분석하고 핵심 내용을 간결하게 정리해주세요."
                },
                {
                    "role": "user", 
                    "content": f"{prompt}\n\n{pdf_content}"
                }
            ],
            "max_completion_tokens": 800,
            "temperature": 0.3,
            "top_p": 1,
            "frequency_penalty": 0,
            "presence_penalty": 0,
            "model": "gpt-4.1"
        }
        
        response = requests.post(
            AZURE_OPENAI_ENDPOINT,
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return f"Azure OpenAI API 오류: {response.status_code}, {response.text}"
    
    except Exception as e:
        return f"요약 과정에서 오류가 발생했습니다: {str(e)}"

def extract_text_from_pdf(pdf_url):
    """
    PDF URL에서 텍스트 내용 추출
    """
    try:
        # PDF 파일 다운로드
        response = requests.get(pdf_url)
        if response.status_code != 200:
            return f"PDF 다운로드 실패: {response.status_code}"
        
        # PDF 파일 읽기
        pdf_file = BytesIO(response.content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        # 텍스트 추출
        text = ""
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            extracted_text = page.extract_text()
            if extracted_text is not None:  # None 체크 추가
                text += extracted_text + "\n\n"
            else:
                text += f"[페이지 {page_num+1}의 텍스트를 추출할 수 없습니다.]\n\n"
        
        if not text.strip():
            return "PDF에서 텍스트를 추출할 수 없습니다. 이미지 기반 PDF이거나 텍스트 레이어가 없는 PDF일 수 있습니다."
        
        return text
    
    except Exception as e:
        return f"PDF 처리 중 오류가 발생했습니다: {str(e)}"

@has_param
def extract_pdf_data(chat: ChatContext):
    """
    PDF 첨부 파일의 데이터를 추출하여 채팅으로 보여주는 기능
    """
    try:
        # 소스 메시지가 있는지 확인
        if not chat.message.source_id:
            chat.reply("PDF가 첨부된 메시지에 답장으로 사용해주세요.")
            return
        
        # 소스 메시지 정보 가져오기
        source = chat.get_source()
        
        # 첨부 파일 데이터 가져오기 (개선된 방식)
        attachment_data = load_attachment(source)
        
        # 첨부 파일 확인
        if not attachment_data:
            chat.reply("PDF 파일이 첨부된 메시지에 답장으로 사용해주세요.")
            return
        
        # 첨부 파일 정보 JSON으로 변환
        attachment_json = json.dumps(attachment_data, ensure_ascii=False, indent=2)
        
        # 결과 출력
        chat.reply(f"첨부 파일 데이터:\n```json\n{attachment_json}\n```\n\n이제 '!pdf요약' 명령어로 PDF를 요약할 수 있습니다.")
    
    except Exception as e:
        chat.reply(f"PDF 데이터 추출 중 오류가 발생했습니다: {str(e)}")

@is_reply
def get_pdf_summary(chat: ChatContext):
    try:
        # 파라미터가 있는 경우 프롬프트로 사용 (None 체크 추가)
        if hasattr(chat.message, "param") and chat.message.param:
            prompt = chat.message.param.strip() if chat.message.param.strip() else "이 PDF 문서의 내용을 핵심만 간략하게 요약해주세요."
        else:
            prompt = "이 PDF 문서의 내용을 핵심만 간략하게 요약해주세요."
        
        # 소스 메시지 정보 가져오기
        source = chat.get_source()
        
        # 첨부 파일 데이터 가져오기 (개선된 방식)
        attachment_data = None
        
        # 1. 소스 메시지에서 직접 첨부 파일 로드 시도
        attachment_data = load_attachment(source)
        
        # 2. 소스 메시지에 첨부 파일이 없다면 메시지 내용에서 JSON 파싱 시도
        if not attachment_data and hasattr(source.message, "msg") and source.message.msg:
            if "{" in source.message.msg and "}" in source.message.msg:
                try:
                    start_idx = source.message.msg.find("{")
                    end_idx = source.message.msg.rfind("}") + 1
                    json_str = source.message.msg[start_idx:end_idx]
                    attachment_data = json.loads(json_str)
                except:
                    pass
        
        # 첨부 파일 확인
        if not attachment_data:
            chat.reply("PDF 파일 데이터를 찾을 수 없습니다. '!pdf데이터' 명령으로 얻은 데이터에 답장으로 사용해주세요.")
            return
        
        # PDF 파일 URL 추출
        if "url" not in attachment_data:
            chat.reply("첨부 파일에서 URL을 찾을 수 없습니다.")
            return
        
        pdf_url = attachment_data["url"]
        pdf_name = attachment_data.get("name", "문서")
        
        # PDF에서 텍스트 추출
        #chat.reply(f"'{pdf_name}' PDF를 분석 중입니다. 잠시만 기다려주세요...")
        pdf_text = extract_text_from_pdf(pdf_url)
        
        if isinstance(pdf_text, str) and pdf_text.startswith("PDF"):
            chat.reply(pdf_text)  # 오류 메시지 반환
            return
        
        # 텍스트가 너무 길면 잘라내기
        max_chars = 15000  # OpenAI API 제한에 맞게 조정
        if len(pdf_text) > max_chars:
            pdf_text = pdf_text[:max_chars] + "... (내용이 너무 길어 일부만 분석합니다)"
        
        # GPT로 요약 생성
        summary = summarize_pdf_with_gpt(pdf_text, prompt)
        
        # 요약 결과 응답
        chat.reply(f"📄 '{pdf_name}' PDF 요약 결과:\n\n{summary}")
    
    except Exception as e:
        chat.reply(f"PDF 요약 중 오류가 발생했습니다: {str(e)}")

def auto_pdf_summary(chat: ChatContext):
    """
    PDF 파일이 올라오면 자동으로 요약하는 기능
    """
    try:
        # PDF 파일 첨부 여부 확인 (메시지 끝에 .pdf가 포함된 경우)
        if not hasattr(chat.message, "msg") or not chat.message.msg:
            return

        msg = chat.message.msg.strip()
        if not msg.lower().endswith('.pdf'):
            return

        # 첨부 파일 데이터 확인
        attachment_data = load_attachment(chat)
        if not attachment_data:
            return

        # PDF 파일 URL 추출
        if "url" not in attachment_data:
            return
        
        pdf_url = attachment_data["url"]
        pdf_name = attachment_data.get("name", "문서")
        
        # PDF에서 텍스트 추출
        #chat.reply(f"'{pdf_name}' PDF를 자동으로 분석 중입니다. 잠시만 기다려주세요...")
        pdf_text = extract_text_from_pdf(pdf_url)
        
        if isinstance(pdf_text, str) and pdf_text.startswith("PDF"):
            chat.reply(pdf_text)  # 오류 메시지 반환
            return
        
        # 텍스트가 너무 길면 잘라내기
        max_chars = 15000  # OpenAI API 제한에 맞게 조정
        if len(pdf_text) > max_chars:
            pdf_text = pdf_text[:max_chars] + "... (내용이 너무 길어 일부만 분석합니다)"
        
        # 기본 프롬프트 사용
        prompt = "이 PDF 문서의 내용을 핵심만 간략하게 요약해주세요."
        
        # GPT로 요약 생성
        summary = summarize_pdf_with_gpt(pdf_text, prompt)
        
        # 요약 결과 응답
        chat.reply(f"📄 '{pdf_name}' PDF 요약 결과:\n\n{summary}")
    
    except Exception as e:
        print(f"자동 PDF 요약 중 오류 발생: {str(e)}")
        # 자동 기능이므로 오류 메시지는 사용자에게 표시하지 않음 