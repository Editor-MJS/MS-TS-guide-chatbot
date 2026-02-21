# -*- coding: utf-8 -*-
"""
==============================================================================
[대웅제약] 챗봇용 네비게이션 인덱스 생성기 (온라인-AI 버전)
==============================================================================
특징: Gemini AI를 활용한 고지능 상황 분석 및 챗봇 가이드 생성
출력: Chatbot_Navigation_Index_Online.pdf
==============================================================================
"""

import os
import sys
import glob
import time
import re
import warnings
import logging

warnings.filterwarnings("ignore")

# 콘솔 인코딩
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

import pypdf
from fpdf import FPDF
from google import genai
from dotenv import load_dotenv

# 환경 설정
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=API_KEY)
MODEL_ID = "gemini-1.5-flash" # 요약용으로 검증된 모델

DIR_TARGET = "Output_Kor" # 분석 대상 폴더
RESULT_FILE = "Chatbot_Navigation_Index_Online.pdf"

FONT_REG = r"C:\Windows\Fonts\malgun.ttf"
FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"

def get_situational_summary(pdf_path, doc_id):
    """AI를 통해 인덱스용 상황 분석을 수행합니다."""
    try:
        reader = pypdf.PdfReader(pdf_path)
        # 앞 레이아웃과 첫 3페이지만 읽어도 흐름 파악 가능
        text = ""
        for i in range(min(len(reader.pages), 3)):
            text += reader.pages[i].extract_text() + "\n"
        
        prompt = f"""당신은 제약 QC 문서 관리 전문가입니다. 
다음 문서를 분석하여 '챗봇이 사용자에게 안내할 가이드'를 만드세요.

문서명: {doc_id}
내용 요약:
{text[:5000]}

작성 형식 (반드시 이 형식을 유지하세요):
문서 ID: {doc_id}
[추천 상황]: (예: 펌프 압력이 요동치거나 체크밸브 오염이 의심될 때)
[핵심 해결책]: (이 문서가 제공하는 핵심 해결 방법 1줄)
[챗봇 안내 멘트]: (사용자에게 이 문서를 어떻게 소개하면 좋을지 챗봇용 말투로 1~2문장)
[매칭 키워드]: (쉼표로 구분한 핵심 단어 5개)
"""
        # API 호출 (재시도 로직 포함)
        for _ in range(3):
            try:
                res = client.models.generate_content(model=MODEL_ID, contents=prompt)
                return res.text.strip()
            except:
                time.sleep(5)
        return "요약 생성 실패"
    except Exception as e:
        return f"파일 분석 에러: {e}"

def create_index_pdf(summaries, out_path):
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_font("Malgun", "", FONT_REG)
    pdf.add_font("Malgun", "B", FONT_BOLD)
    pdf.add_page()
    
    pdf.set_font("Malgun", "B", 18)
    pdf.set_text_color(40, 40, 120)
    pdf.cell(0, 20, "QC 챗봇 네비게이션 가이드 (AI 분석)", ln=1, align="C")
    pdf.set_font("Malgun", "", 10)
    pdf.set_text_color(100)
    pdf.cell(0, 5, f"생성일시: {time.strftime('%Y-%m-%d %H:%M:%S')}", ln=1, align="R")
    pdf.ln(10)

    for s in summaries:
        if pdf.get_y() > 240: pdf.add_page()
        
        # 구분선
        pdf.set_draw_color(200, 200, 220)
        pdf.set_fill_color(245, 245, 250)
        pdf.rect(10, pdf.get_y(), 190, 8, style='F') # style='F'로 수정
        
        pdf.set_font("Malgun", "B", 11)
        pdf.set_text_color(30, 70, 140)
        
        sections = s.split("\n")
        doc_title = sections[0] if sections else "Unknown Doc"
        pdf.cell(0, 8, f" {doc_title}", ln=1)
        
        pdf.set_font("Malgun", "", 9)
        pdf.set_text_color(50)
        
        for line in sections[1:]:
            if line.strip():
                if "[" in line and "]" in line: # 항목 헤더 강조
                    pdf.set_font("Malgun", "B", 9)
                    pdf.write(6, line.split("]")[0] + "]")
                    pdf.set_font("Malgun", "", 9)
                    pdf.write(6, line.split("]")[1] + "\n")
                else:
                    # 가로 너비를 190으로 명시하여 계산 오류 해결
                    pdf.multi_cell(190, 6, line.strip())
        pdf.ln(6)
        
    pdf.output(out_path)

def main():
    print("\n[AI 인덱스 생성기 시작]")
    pdf_files = glob.glob(os.path.join(DIR_TARGET, "*.pdf"))
    if not pdf_files:
        print(f"'{DIR_TARGET}' 폴더에 분석할 PDF가 없습니다.")
        return

    all_summaries = []
    for f in pdf_files:
        fname = os.path.basename(f)
        if "en" in fname.lower(): continue # 영문판은 제외하고 국문판만 분석
        
        print(f"▶ {fname} 분석 중...")
        doc_id = fname.replace(".pdf", "")
        summary = get_situational_summary(f, doc_id)
        all_summaries.append(summary)
        time.sleep(2) # 쿼터 방지

    if all_summaries:
        create_index_pdf(all_summaries, RESULT_FILE)
        print(f"\n최종 인덱스가 완성되었습니다: {RESULT_FILE}")

if __name__ == "__main__":
    main()
