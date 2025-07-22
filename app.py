import streamlit as st
import company_codes

import requests
from bs4 import BeautifulSoup
import re
import fitz  # PyMuPDF

import os
from dotenv import load_dotenv

# Gemini API用（仮のimport。実際のAPIクライアントに合わせて修正してください）
from google.generativeai import GenerativeModel
import google.generativeai as genai

# .envからAPIキーを取得
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Gemini APIキーを設定
genai.configure(api_key=GOOGLE_API_KEY)

# """  企業名から企業コードを取得する関数 """
def get_company_code(company_name):
    code = company_codes.company_codes.get(company_name)
    return code

# """ 企業コードから有価証券報告書PDFを取得する関数 """
def fetch_securities_report_pdf(code):
    url = "https://www.nikkei.com/nkd/company/ednr/?scode=" + code
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    # 「有価証券報告書」を含むリンクを抽出
    links = soup.find_all("a", string=re.compile("有価証券報告書"))
    pdf_url = None
    for link in links:
        href = link.get("href")
        full_url = requests.compat.urljoin(url, href)

        # ページを取得
        res2 = requests.get(full_url, headers=headers)
        soup2 = BeautifulSoup(res2.text, "html.parser")
        script_text = "".join([script.get_text() for script in soup2.find_all("script")])
        match = re.search(r"window\['pdfLocation'\]\s*=\s*\"(.*?)\"", script_text)
        if match:
            pdf_path = match.group(1)
            pdf_url = "https://www.nikkei.com" + pdf_path
            break

    if pdf_url:
        pdf_response = requests.get(pdf_url, headers=headers)
        with open("securities_report.pdf", "wb") as f:
            f.write(pdf_response.content)
        return pdf_url, "securities_report.pdf"
    else:
        return None, None


# """ PDFからテキスト抽出・要約プロンプト生成・Gemini API呼び出し関数 """
def summarize_securities_report(pdf_url, company_name, gemini_api_key):
    # 1. PDFデータをダウンロード
    response = requests.get(pdf_url)
    response.raise_for_status()

    # 2. fitz で PDF を読み込む
    doc = fitz.open(stream=response.content, filetype="pdf")

    # 3. テキスト抽出
    text = ""
    for page in doc:
        text += page.get_text()

    # 4. プロンプトファイルを読み込む
    with open("prompt.txt", "r", encoding="utf-8") as f:
        prompt_template = f.read()

    max_chars = 90000
    prompt_text = prompt_template.replace("[企業名を入力]", company_name) + "\n" + text[:max_chars]

    # 5. Gemini APIで要約を取得
    model = GenerativeModel(model_name="gemini-2.5-pro")
    response = model.generate_content(prompt_text)

    # 6. 結果を返す
    return response.text




# """ UI部分 """

# サイドバーUI
with st.sidebar:
    st.header("企業情報入力")
    company_name = st.text_input("企業名を入力してください")
    department_name = st.text_input("顧客担当者の部署名を入力してください")
    position_name = st.text_input("顧客担当者の役職を入力してください（例：部長、課長、担当者など）")
    search_button = st.button("有価証券報告書を検索")

# メインUI
st.title("有価証券報告書AIサマリー＆仮説立て")


# セッションステートで出力内容を保持
if 'summary' not in st.session_state:
    st.session_state.summary = None
if 'hypothesis' not in st.session_state:
    st.session_state.hypothesis = None
if 'hearing_items' not in st.session_state:
    st.session_state.hearing_items = None

if search_button and company_name:
    code = get_company_code(company_name)
    if code:
        with st.spinner("有価証券報告書PDFを取得中..."):
            pdf_url, pdf_path = fetch_securities_report_pdf(code)
        if pdf_url:
            with st.spinner("🔍 有価証券報告書を要約中...(1/3)"):
                st.session_state.summary = summarize_securities_report(pdf_url, company_name, GOOGLE_API_KEY)
            if department_name and position_name:
                with st.spinner("🤔 担当者の課題仮説立て考え中...(2/3)"):
                    with open("hypothesis_prompt.txt", "r", encoding="utf-8") as f:
                        hypo_template = f.read()
                    hypo_prompt = hypo_template.replace("{securities_report_summary}", st.session_state.summary)
                    hypo_prompt = hypo_prompt.replace("{department_name}", department_name)
                    hypo_prompt = hypo_prompt.replace("{position_title}", position_name)
                    model = GenerativeModel(model_name="gemini-2.5-pro")
                    response = model.generate_content(hypo_prompt)
                    st.session_state.hypothesis = response.text
                    st.write("【DEBUG】hypothesis:", st.session_state.hypothesis)

                # ヒアリング項目AI提案
                with st.spinner("👂 ヒアリング項目出力中...(3/3)"):
                    with open("hearing_prompt.txt", "r", encoding="utf-8") as f:
                        hearing_template = f.read()
                    # 企業規模・業界は現状空欄で渡す
                    hearing_prompt = hearing_template.replace("{company_name}", company_name)
                    hearing_prompt = hearing_prompt.replace("{department_name}", department_name)
                    hearing_prompt = hearing_prompt.replace("{position_name}", position_name)
                    hearing_prompt = hearing_prompt.replace("{company_size}", "")
                    hearing_prompt = hearing_prompt.replace("{industry}", "")
                    hearing_prompt = hearing_prompt.replace("{hypothesis}", st.session_state.hypothesis)
                    model = GenerativeModel(model_name="gemini-2.5-pro")
                    hearing_response = model.generate_content(hearing_prompt)
                    st.session_state.hearing_items = hearing_response.text
                    st.write("【DEBUG】hearing_items:", st.session_state.hearing_items)
            st.success("✅ PDFリンクを取得しました！")
            st.write(f"PDFリンク: {pdf_url}")
            st.write(f"PDFファイル名: {pdf_path}")
            st.download_button(
                label="PDFをダウンロード",
                data=open(pdf_path, "rb").read(),
                file_name=pdf_path,
                mime="application/pdf"
            )
        else:
            st.error("❌ PDFリンクが見つかりませんでした。")
    else:
        st.write("指定された企業名が辞書に存在しません。先に企業コードを登録してください。")

# タブ切り替えで要約・仮説・ヒアリング項目を表示
if st.session_state.summary or st.session_state.hypothesis or st.session_state.hearing_items:
    tabs = st.tabs(["有価証券報告書要約", "仮説立て（担当者課題）", "ヒアリング項目提案"])
    with tabs[0]:
        if st.session_state.summary:
            st.subheader("Gemini要約結果")
            st.write(st.session_state.summary)
    with tabs[1]:
        if st.session_state.hypothesis:
            st.subheader("AI仮説・担当者課題提案")
            st.write(st.session_state.hypothesis)
    with tabs[2]:
        if st.session_state.hearing_items:
            st.subheader("訪問時のヒアリング項目（AI提案）")
            st.write(st.session_state.hearing_items)
