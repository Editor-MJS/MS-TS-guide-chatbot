import pandas as pd
import os

def get_index_context():
    """엑셀 가중치 인덱스를 로드하여 텍스트 컨텍스트로 변환"""
    folder = "인덱스_가중치_모음"
    files = ["HPLC_가중치 인덱스.xlsx", "UPLC_가중치 인덱스.xlsx"]
    
    context = "## [SYSTEM INDEX DATA]\n"
    
    for f in files:
        path = os.path.join(folder, f)
        if os.path.exists(path):
            instrument = f.split("_")[0]
            try:
                df = pd.read_excel(path)
                # 불필요한 공백 제거 및 문자열 변환
                df = df.fillna("")
                
                context += f"\n### INSTRUMENT: {instrument}\n"
                # 데이터프레임을 텍스트 형태로 변환 (Gemini가 읽기 좋게)
                for _, row in df.iterrows():
                    context += f"- DocNo: {row.get('문서 번호', '')} | Fix: {row.get('핵심 해결방법', '')} | Symptom: {row.get('발생 상황', '')} | InternalRank: {row.get('문서 내 순위', '')} | Weight: {row.get('절대 가중치', '')} | Reasoning: {row.get('비고', '')}\n"
            except Exception as e:
                context += f"\nError loading {f}: {str(e)}\n"
        else:
            context += f"\nFile not found: {f}\n"
            
    return context
