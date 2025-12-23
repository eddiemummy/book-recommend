# ==== app.py ==============================================================
import json
from urllib.parse import quote_plus
import os
import streamlit as st
from langchain_core.prompts import PromptTemplate

from gemini import create_model



def goodreads_search_url(title: str, author: str = "") -> str:
    q = f"{title} {author}".strip()
    return f"https://www.goodreads.com/search?q={quote_plus(q)}"


# -------------------------- helpers --------------------------------------
def normalize_title(s: str) -> str:
    return " ".join(str(s).strip().lower().split())


def safe_json_loads(s: str):
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.strip().strip("`").strip()
        if s.lower().startswith("json"):
            s = s.split("\n", 1)[-1].strip()
    return json.loads(s)


def get_read_set() -> set[str]:
    if "read_set" not in st.session_state:
        st.session_state.read_set = set()
    return st.session_state.read_set


def set_read_set(items: set[str]):
    st.session_state.read_set = items


def replace_read_from_uploaded_text(content: str):
    lines = [l.strip() for l in (content or "").splitlines()]
    items = {l for l in lines if l}
    set_read_set(items)


def append_read(title: str):
    title = (title or "").strip()
    if not title:
        return
    rs = get_read_set()
    rs.add(title)
    set_read_set(rs)


def export_read_txt() -> str:
    rs = get_read_set()
    if not rs:
        return ""
    return "\n".join(sorted(rs)) + "\n"


def filter_out_read(recs: list[dict], read_set: set[str]) -> list[dict]:
    read_norm = {normalize_title(x) for x in read_set}
    out = []
    seen = set()

    for r in recs:
        title = str(r.get("title", "")).strip()
        author = str(r.get("author", "")).strip()
        reason = str(r.get("reason", "")).strip()

        if not title:
            continue

        key = normalize_title(title)
        if key in read_norm:
            continue
        if key in seen:
            continue
        seen.add(key)

        out.append({"title": title, "author": author, "reason": reason})

    return out


# -------------------------- UI -------------------------------------------
st.set_page_config(page_title="Kitap Öneri Botu", layout="wide")
st.title("📚 Kitap Öneri Botu")
st.caption("Query yaz → 10 öneri gelir → Okudum → read.txt güncellenir → Download ile indirip sonra tekrar upload edebilirsin.")

# --- Import/Export read.txt (overwrite semantics) ---
st.divider()
st.subheader("📦 read.txt yükle / indir")
st.markdown(
    """
**ℹ️ Kullanım Bilgisi**

- Eğer **sıfırdan başlamak istiyorsanız**, hiçbir şey yüklemeden devam edin.  
  Okudukça listeniz oluşturulacak ve **yeni bir `read.txt` üretilecektir**.

- Eğer **mevcut listenizi güncellemek istiyorsanız**, daha önce kullandığınız `.txt` dosyanızı yükleyin.  
  Dosyanın adı **`read.txt` olmak zorunda değil** — sistem onu otomatik olarak `read.txt` olarak ele alır.

⬇️ İndirdiğiniz dosya her zaman **güncel `read.txt`** olacaktır.
"""
)

col1, col2, col3 = st.columns([2, 2, 2])

with col1:
    uploaded = st.file_uploader(
        "Okuma listenizi yükleyin (.txt) — mevcut listeyi ÜZERİNE YAZAR",
        type=["txt"],
        accept_multiple_files=False,
    )
    if uploaded is not None:
        content = uploaded.getvalue().decode("utf-8", errors="ignore")
        replace_read_from_uploaded_text(content)
        st.success(f"Dosya yüklendi. Toplam kitap: {len(get_read_set())}")
        st.rerun()

with col2:
    if st.button("📄 read listesini göster"):
        rs = get_read_set()
        st.info("\n".join(sorted(rs)) if rs else "Liste boş.")

with col3:
    st.download_button(
        label="⬇️ Güncel read.txt indir",
        data=export_read_txt().encode("utf-8"),
        file_name="read.txt",
        mime="text/plain",
        use_container_width=True,
        disabled=(len(get_read_set()) == 0),
    )

st.divider()

# -------------------------- LLM init (Gemini) -----------------------------
if "llm" not in st.session_state:
    try:
        st.session_state.llm = create_model(temperature=0.0)
    except Exception as e:
        st.error(str(e))
        st.stop()

prompt = PromptTemplate.from_template(
    """
REASON TÜRKÇE OLSUN.
Sen bir kitap öneri asistanısın.

Kullanıcı isteği:
{question}

Kullanıcının daha önce okudukları (ASLA önermeyeceksin):
{read_list}

Amaç:
- Kullanıcının isteğine uygun TAM 10 kitap öner.
- Önerdiğin kitaplar belli bir coğrafyaya sıkışmasın. Dünya edebiyatından seçkiler olsun.
- Okunan kitapları ve çok benzer başlıkları önermemeye çalış.
- Her kitap için 1 cümlelik, SOMUT bir "neden önerildi" açıklaması yaz.
  (Tema, uzunluk, tür, ton, anlatım gibi unsurlardan en az birine bağla.)

Aşağıda format ve açıklama tarzı için SADECE BİR ÖRNEK var (TEKRAR ETME):

{{
  "recommendations": [
    {{
      "title": "Anathem",
      "author": "Neal Stephenson",
      "reason": "Felsefi ve düşünce odaklı yapısı, anlam arayışını bilim kurgu çerçevesinde ele aldığı için kullanıcının sorgulayıcı temasına uygundur."
    }}
  ]
}}

ŞİMDİ GERÇEK ÇIKTIYI ÜRET:
- Yukarıdaki örneği TEKRAR ETME
- Sadece aşağıdaki JSON formatında cevap ver
- recommendations TAM 10 eleman içersin
- Her kitapta reason alanı DOLU olsun

JSON FORMAT:
{{
  "recommendations": [
    {{"title": "Book Title", "author": "Author Name", "reason": "1 cümlelik neden"}},
    ...
  ]
}}
"""
)

chain = prompt | st.session_state.llm

question = st.text_area(
    "Ne okumak istiyorsun? (Her şeyi buraya yaz.)",
    placeholder="Örn: Varoluş temalı, kısa, roman formunda, ağır olmayan bir şey öner.",
    height=130,
)

colA, colB = st.columns([1, 1])
with colA:
    run_button = st.button("10 Öneri Getir", type="primary")
with colB:
    if st.button("🧹 read listesini temizle"):
        set_read_set(set())
        st.success("Okunanlar listesi temizlendi.")
        st.rerun()

# state for last recommendations
if "last_recs" not in st.session_state:
    st.session_state.last_recs = []

if run_button and question.strip():
    read_set = get_read_set()
    read_list = "\n".join(sorted(read_set)) if read_set else "(boş)"

    with st.spinner("Öneriler hazırlanıyor…"):
        msg = chain.invoke({"question": question.strip(), "read_list": read_list})
        raw = getattr(msg, "content", str(msg)).strip()

        try:
            data = safe_json_loads(raw)
            recs = data.get("recommendations", [])
            if not isinstance(recs, list):
                raise ValueError("recommendations list değil")

            recs = filter_out_read(recs, read_set)
            st.session_state.last_recs = recs[:10]

        except Exception:
            st.error("LLM çıktısı parse edilemedi. Raw çıktıyı aşağıda gösteriyorum:")
            st.code(raw)
            st.stop()

# -------------------------- render recommendations ------------------------
if st.session_state.last_recs:
    st.subheader("📋 Öneriler (Okudum → read listesine ekle)")

    read_set_now = get_read_set()
    read_norm_now = {normalize_title(x) for x in read_set_now}

    for idx, r in enumerate(st.session_state.last_recs, start=1):
        title = str(r.get("title", "")).strip()
        author = str(r.get("author", "")).strip()
        reason = str(r.get("reason", "")).strip()

        if not title:
            continue

        already = normalize_title(title) in read_norm_now
        left, right = st.columns([6, 1])

        with left:
            header = f"**{idx}. {title}**"
            if author:
                header += f" — {author}"
            st.markdown(header)

            if reason:
                st.markdown(f"— _{reason}_")
            else:
                st.markdown("— _Neden önerildi: (LLM açıklama vermedi)_")

            url = goodreads_search_url(title, author)
            st.markdown(f"[🔎 Goodreads'te ara]({url})")

        with right:
            if already:
                st.button("✅ Okundu", key=f"done_{idx}", disabled=True)
            else:
                if st.button("✅ Okudum", key=f"read_{idx}"):
                    append_read(title)
                    st.session_state.last_recs = [
                        x for x in st.session_state.last_recs
                        if normalize_title(x.get("title", "")) != normalize_title(title)
                    ]
                    st.rerun()
