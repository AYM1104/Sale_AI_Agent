import streamlit as st
import company_codes

import requests
from bs4 import BeautifulSoup
import re

"""  企業名から企業コードを取得する関数 """
def get_company_code(company_name):
    code = company_codes.company_codes.get(company_name)
    return code

""" 企業コードから有価証券報告書PDFを取得する関数 """
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




""" UI部分 """
st.title("有価証券報告書を要約してくれるAIエージェント")

st.write("こんにちは、顧客訪問前に顧客理解に努めましょう！")

company_name = st.text_input("企業名を入力してください")
if company_name:
    st.write(f"入力された企業名: {company_name}")

search_button = st.button("有価証券報告書を検索")
# ボタンがクリックされたら、以下を実行
if search_button and company_name:
    code = get_company_code(company_name)   # 企業コードを取得する関数
    if code:
        st.write(f"{company_name} のコードは {code} です")
    else:
        st.write("指定された企業名が辞書に存在しません。先に企業コードを登録してください。")

    # 「www.nikkei.com」から対象企業のページを取得
