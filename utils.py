import pandas as pd
import os
import streamlit as st
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from dotenv import load_dotenv

load_dotenv()

@st.cache_resource
def get_vector_db():
    folder = "인덱스_가중치_모음"
    files = ["HPLC_가중치 인덱스.xlsx", "UPLC_가중치 인덱스.xlsx"]
    
    docs = []
    
    for f in files:
        path = os.path.join(folder, f)
        if os.path.exists(path):
            instrument = f.split("_")[0]
            try:
                df = pd.read_excel(path).fillna("")
                for _, row in df.iterrows():
                    doc_no = str(row.get('문서 번호', '')).strip()
                    fix = str(row.get('핵심 해결방법', ''))
                    symptom = str(row.get('발생 상황', ''))
                    rank = str(row.get('문서 내 순위', ''))
                    weight = str(row.get('절대 가중치', ''))
                    reasoning = str(row.get('비고', ''))
                    
                    # AI가 검색할 기반이 되는 텍스트
                    content = f"장비: {instrument} | 현상: {symptom} | 원인 및 해결방법: {fix} | 설명: {reasoning}"
                    
                    # 메타데이터 (답변 생성 시 활용)
                    metadata = {
                        "instrument": instrument,
                        "doc_no": doc_no,
                        "fix": fix,
                        "symptom": symptom,
                        "rank": rank,
                        "weight": weight,
                        "reasoning": reasoning
                    }
                    docs.append(Document(page_content=content, metadata=metadata))
            except Exception as e:
                print(f"Error loading {f}: {e}")
                
    if not docs:
        return None
        
    # [핵심] 구글 API 대신 로컬에서 직접 연산하는 모델 사용 (한도 에러 원천 차단)
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vector_db = FAISS.from_documents(docs, embeddings)
    return vector_db

