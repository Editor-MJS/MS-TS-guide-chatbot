# -*- coding: utf-8 -*-
"""
==============================================================================
[대웅제약] 분석기기 자동화 시스템 v8.0 (100% Offline Version)
==============================================================================
본 프로그램은 인터넷 연결 없이 사용자 PC 내부에서만 작동하는 오프라인 버전입니다.
작업 프로토콜:
1. 'Input_Excel_offline' 폴더에 분석할 엑셀 파일을 넣습니다.
2. '클릭하여_오프라인_자동화_실행.bat'을 실행합니다.
3. 데이터가 외부로 절대 유출되지 않으며 PC 내부에서 번역이 진행됩니다.
==============================================================================
"""

import os
import sys
import glob
import re
import traceback
import warnings
import time

# 라이브러리 경고 숨기기
warnings.filterwarnings("ignore")

# Windows Console Encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

import win32com.client

# 오프라인 번역 엔진 시도
try:
    import argostranslate.package
    import argostranslate.translate
    OFFLINE_AVAILABLE = True
except ImportError:
    OFFLINE_AVAILABLE = False

# ──────────────────────────────────────────────────────────────
# 설정 (오프라인 전용 폴더)
# ──────────────────────────────────────────────────────────────
DIR_INPUT = "Input_Excel_offline"
DIR_KOR = "Output_Kor_offline"
DIR_EN = "Output_en_offline"

# ──────────────────────────────────────────────────────────────
# [오프라인 번역] 로컬 엔진 설정
# ──────────────────────────────────────────────────────────────
def setup_offline_engine():
    """최초 실행 시 오프라인 번역 패키지를 설치합니다."""
    if not OFFLINE_AVAILABLE:
        print("[오류] 'argostranslate' 패키지가 설치되어 있지 않습니다.")
        print("명령어: pip install argostranslate")
        return False
    
    try:
        from_code = "ko"
        to_code = "en"
        
        # 이미 설치되어 있는지 확인
        installed_languages = argostranslate.translate.get_installed_languages()
        from_lang = list(filter(lambda x: x.code == from_code, installed_languages))
        to_lang = list(filter(lambda x: x.code == to_code, installed_languages))
        
        if from_lang and to_lang:
            return True
            
        print("[안내] 오프라인 번역 모델이 없습니다. 최초 1회 다운로드를 시도합니다...")
        print("(이 과정에서만 잠시 인터넷이 필요하며, 이후에는 100% 오프라인으로 작동합니다.)")
        
        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()
        package_to_install = next(
            filter(lambda x: x.from_code == from_code and x.to_code == to_code, available_packages)
        )
        argostranslate.package.install_from_path(package_to_install.download())
        print("[완료] 오프라인 모델 설치 성공!")
        return True
    except Exception as e:
        print(f"[오류] 오프라인 모델 설정 실패: {e}")
        return False

def translate_offline(text):
    if not text or not str(text).strip(): return text
    if not re.search('[가-힣]', str(text)): return text
    
    try:
        # 로컬 엔진으로 번역 (PC 밖으로 데이터가 나가지 않음)
        return argostranslate.translate.translate(text, "ko", "en")
    except:
        return text

# ──────────────────────────────────────────────────────────────
# [핵심] 엑셀 직접 번역 및 PDF 변환 엔진
# ──────────────────────────────────────────────────────────────
def process_excel_offline(input_path, doc_id):
    excel = None
    wb = None
    try:
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        
        abs_input = os.path.abspath(input_path)
        wb = excel.Workbooks.Open(abs_input)
        
        # --- [1단계] 한글 PDF 저장 ---
        kor_pdf_path = os.path.abspath(os.path.join(DIR_KOR, f"{doc_id}.pdf"))
        for sh in wb.Sheets:
            sh.PageSetup.Orientation = 2 # Landscape
            sh.PageSetup.FitToPagesWide = 1
            sh.PageSetup.FitToPagesTall = False

        wb.ExportAsFixedFormat(0, kor_pdf_path)
        print(f"  - STEP 1: Korean PDF saved (Offline)")

        # --- [2단계] 셀 텍스트 로컬 번역 ---
        print(f"  - STEP 2: Translating cells LOCALLY...", end="", flush=True)
        for sh in wb.Sheets:
            used = sh.UsedRange
            if not used: continue
            for cell in used:
                if cell.Value and isinstance(cell.Value, str):
                    cell.Value = translate_offline(cell.Value)
        print(" Done")

        # --- [3단계] 영어 PDF 저장 ---
        en_pdf_path = os.path.abspath(os.path.join(DIR_EN, f"{doc_id} en.pdf"))
        wb.ExportAsFixedFormat(0, en_pdf_path)
        print(f"  - STEP 3: English PDF saved (Offline)")
        
        return True

    except Exception as e:
        print(f"    [Error] Processing fail: {e}")
        return False
    finally:
        if wb: wb.Close(False)
        if excel: excel.Quit()

# ──────────────────────────────────────────────────────────────
# 메인 엔진
# ──────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print("  Daewoong QC Automation System v8.0 (100% OFFLINE)")
    print(f"{'='*60}")

    # 엔진 설정 확인
    if not setup_offline_engine():
        print("\n[알림] 오프라인 엔진을 초기화할 수 없습니다. 설정을 확인해 주세요.")
        input("\n계속하려면 엔터를 누르세요...") # 창 닫힘 방지
        return

    # 폴더 준비
    for d in [DIR_INPUT, DIR_KOR, DIR_EN]:
        os.makedirs(d, exist_ok=True)

    excel_files = sorted(glob.glob(os.path.join(DIR_INPUT, "*.xlsx")))
    excel_files = [f for f in excel_files if not os.path.basename(f).startswith("~$")]

    if not excel_files:
        print(f"\n[Empty] Please put original files in '{DIR_INPUT}' folder.")
        return

    print(f"\n[Offline Process Target: {len(excel_files)} file(s)]")
    
    for f in excel_files:
        fname = os.path.basename(f)
        match = re.search(r'([A-Za-z]+[-_\s]?\d+)', fname)
        doc_id = match.group(1).replace(" ", "_").upper() if match else fname.split(".")[0]
        
        print(f"\n▶ [{doc_id}] Offline Processing Start...")
        success = process_excel_automation = process_excel_offline(f, doc_id)
        
        if success:
            print(f"  ✅ SUCCESS: {doc_id} work finished offline.")
        else:
            print(f"  ❌ FAILED: {doc_id}")

    print(f"\n{'='*60}")
    print("  All offline operations finished safely.")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
