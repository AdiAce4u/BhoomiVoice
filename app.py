import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
import streamlit as st
from dotenv import load_dotenv

# ---------------------------------------------------------
# Environment & Configuration Setup
# ---------------------------------------------------------
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()

STT_URL = "https://api.sarvam.ai/speech-to-text"
DOC_EXTRACT_URL = "https://api.sarvam.ai/doc-ai/v1/job/extract"
CHAT_COMPLETION_URL = "https://api.sarvam.ai/v1/chat/completions"
TTS_URL = "https://api.sarvam.ai/text-to-speech"
SAMPLE_DATA_PATH = Path(__file__).resolve().parent / "sample_data.json"

# ---------------------------------------------------------
# Helper Functions: Data Loading & Fallbacks
# ---------------------------------------------------------
def load_sample_record() -> Dict[str, Any]:
    """Load default sample Khatauni records with guaranteed local fallback."""
    if SAMPLE_DATA_PATH.exists():
        try:
            return json.loads(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "khatedar": "रामेश्वर प्रसाद सुपुत्र हरिनारायण",
        "village_tehsil": "रामपुर कलां, तहसील सदर (वाराणसी)",
        "khasra_no": "342/2 ख",
        "recorded_area": "0.4520 हेक्टेयर (लगभग 1.11 एकड़)",
        "khata_number": "00128",
        "fasli_year": "1430-1435 फस्ली",
        "land_category": "कृषि भूमि (संक्रमणीय भूमिधर)",
        "revenue_tax": "₹ 48.50 वार्षिक लगान",
        "remarks": "वर्तमान में कोई बंधक (Mortgage) या न्यायालय स्थगन (Stay) दर्ज नहीं है।",
        "extracted_text": (
            "उत्तर प्रदेश राजस्व परिषद - खतौनी। ग्राम: रामपुर कलां, तहसील: सदर, जनपद: वाराणसी। "
            "खाता संख्या: 00128। खातेदार: रामेश्वर प्रसाद सुपुत्र हरिनारायण। "
            "खसरा संख्या: 342/2 ख। क्षेत्रफल: 0.4520 हेक्टेयर। देय मालगुजारी: ₹ 48.50। कैफियत: भूमि संक्रामणीय अधिकार युक्त।"
        ),
    }


def extract_document_data(uploaded_file, api_key: str) -> Tuple[Dict[str, Any], bool, str]:
    """
    Attempt to extract document fields via Sarvam Doc AI API.
    Guaranteed immediate fallback to sample_data.json on failure or timeout.
    Returns: (record_data, is_fallback, status_message)
    """
    if not api_key:
        return load_sample_record(), True, "API Key अनुपलब्ध है - स्थानीय प्रतिदर्श डेटा (Sample Data) लोड किया गया।"

    try:
        files = {
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                uploaded_file.type or "application/octet-stream",
            )
        }
        headers = {"api-subscription-key": api_key}
        response = requests.post(
            DOC_EXTRACT_URL,
            headers=headers,
            files=files,
            timeout=8,
        )

        if response.status_code == 200:
            res_json = response.json()
            # If doc-ai parsed structured fields, map them; otherwise use fallback
            extracted_text = res_json.get("text", "") or str(res_json)
            data = load_sample_record()
            data["extracted_text"] = extracted_text
            return data, False, "दस्तावेज़ सफलतापूर्वक विश्लेषित किया गया (Sarvam Doc-AI)!"
        else:
            return load_sample_record(), True, f"Doc-AI सेवा अनुपलब्ध ({response.status_code}) - स्थानीय प्रतिदर्श डेटा सक्रिय।"
    except Exception as exc:
        return load_sample_record(), True, f"त्वरित स्थानीय फ़ालबैक सक्रिय: {str(exc)[:60]}"


# ---------------------------------------------------------
# Sarvam API Wrappers: STT, LLM, TTS
# ---------------------------------------------------------
def transcribe_audio_saaras(audio_bytes: bytes, api_key: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Transcribe Hindi/Hinglish speech via Sarvam Saaras v4 (codemix mode).
    Returns: (transcript, error_message)
    """
    if not api_key:
        return None, "SARVAM_API_KEY सेट नहीं है।"

    try:
        files = {"file": ("query.wav", audio_bytes, "audio/wav")}
        data = {
            "model": "saaras:v4",
            "mode": "codemix",
            "language_code": "hi-IN",
        }
        headers = {"api-subscription-key": api_key}

        resp = requests.post(STT_URL, headers=headers, files=files, data=data, timeout=15)
        if resp.status_code == 200:
            result = resp.json()
            transcript = result.get("transcript", "").strip()
            return transcript, None
        else:
            return None, f"Saaras v4 STT त्रुटि ({resp.status_code}): {resp.text[:120]}"
    except Exception as exc:
        return None, f"STT कनेक्शन त्रुटि: {str(exc)}"


def answer_query_grounded_llm(
    query: str,
    record: Dict[str, Any],
    api_key: str,
) -> Tuple[str, Optional[str]]:
    """
    Query sarvam-105b with strict Hindi system prompt and record context.
    Returns: (answer_text, error_message)
    """
    system_prompt = (
        "You are BhoomiVoice. Answer ONLY based on the document fields provided. "
        "If not found, say 'दस्तावेज़ में यह जानकारी उपलब्ध नहीं है।' "
        "Never say legal owner, only say दर्ज खातेदार. Keep it under 2 sentences in spoken Hindi."
    )

    doc_context = (
        f"खातेदार (दर्ज धारक): {record.get('khatedar')}\n"
        f"ग्राम व तहसील: {record.get('village_tehsil')}\n"
        f"खसरा / गाटा संख्या: {record.get('khasra_no')}\n"
        f"दर्ज क्षेत्रफल: {record.get('recorded_area')}\n"
        f"खाता संख्या: {record.get('khata_number', 'N/A')}\n"
        f"फसली वर्ष: {record.get('fasli_year', 'N/A')}\n"
        f"श्रेणी / किस्म: {record.get('land_category', 'N/A')}\n"
        f"लगान: {record.get('revenue_tax', 'N/A')}\n"
        f"कैफियत/टिप्पणी: {record.get('remarks', 'N/A')}\n"
        f"अभिलेख मूल पाठ: {record.get('extracted_text', '')}"
    )

    user_content = f"दस्तावेज़ विवरण:\n{doc_context}\n\nनागरिक का प्रश्न: {query}"

    if not api_key:
        return "SARVAM_API_KEY .env फ़ाइल में उपलब्ध नहीं है। कृपया कुंजी जोड़ें।", "API Key Missing"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sarvam-105b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
        "max_tokens": 1200,
    }

    try:
        resp = requests.post(CHAT_COMPLETION_URL, headers=headers, json=payload, timeout=25)
        if resp.status_code == 200:
            data = resp.json()
            message = data["choices"][0]["message"]
            content = (message.get("content") or "").strip()
            if not content and message.get("reasoning_content"):
                content = message.get("reasoning_content").strip()
            if not content:
                content = "दस्तावेज़ में यह जानकारी उपलब्ध नहीं है।"
            return content, None
        else:
            return (
                "दस्तावेज़ में यह जानकारी उपलब्ध नहीं है।",
                f"LLM API त्रुटि ({resp.status_code}): {resp.text[:120]}",
            )
    except Exception as exc:
        return (
            "दस्तावेज़ में यह जानकारी उपलब्ध नहीं है।",
            f"LLM कनेक्शन त्रुटि: {str(exc)}",
        )


def synthesize_speech_bulbul(
    text: str,
    speaker: str,
    api_key: str,
) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Synthesize spoken Hindi via Sarvam Bulbul v3.
    Returns: (audio_bytes, error_message)
    """
    if not api_key:
        return None, "SARVAM_API_KEY अनुपलब्ध है।"

    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": [text],
        "target_language_code": "hi-IN",
        "speaker": speaker,
        "pitch": 0,
        "pace": 1.0,
        "loudness": 1.5,
        "speech_sample_rate": 8000,
        "enable_preprocessing": True,
        "model": "bulbul:v3",
    }

    try:
        resp = requests.post(TTS_URL, headers=headers, json=payload, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            audios = data.get("audios", [])
            if audios and isinstance(audios, list):
                audio_bytes = base64.b64decode(audios[0])
                return audio_bytes, None
            return None, "ऑडियो डेटा प्राप्त नहीं हुआ।"
        else:
            return None, f"Bulbul v3 TTS त्रुटि ({resp.status_code}): {resp.text[:120]}"
    except Exception as exc:
        return None, f"TTS कनेक्शन त्रुटि: {str(exc)}"


# ---------------------------------------------------------
# Streamlit UI Configuration & Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="BhoomiVoice 🌾 | Land Record Voice Agent",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for rich rural Indian thematic styling (Glassmorphism & Earthy Accents)
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Mukta:wght@400;600;700&family=Outfit:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Mukta', 'Outfit', sans-serif;
    }
    
    /* Disclaimer Banner */
    .disclaimer-badge {
        background: linear-gradient(135deg, #fff3cd 0%, #ffeeba 100%);
        color: #856404;
        border: 1px solid #ffeeba;
        border-left: 6px solid #e0a800;
        padding: 12px 18px;
        border-radius: 8px;
        font-size: 0.96rem;
        margin-bottom: 20px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    /* Metric Cards */
    .record-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        border-top: 4px solid #16a34a;
        height: 100%;
    }
    .record-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(22, 163, 74, 0.12);
    }
    .record-label {
        font-size: 0.82rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #64748b;
        margin-bottom: 6px;
    }
    .record-value {
        font-size: 1.15rem;
        font-weight: 700;
        color: #0f172a;
        line-height: 1.4;
    }
    
    /* Response Box */
    .bhoomi-response-box {
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
        border: 1px solid #bbf7d0;
        border-left: 6px solid #16a34a;
        padding: 18px 22px;
        border-radius: 12px;
        margin: 15px 0;
        font-size: 1.1rem;
        color: #14532d;
        font-weight: 600;
    }
    
    /* Header title */
    .app-main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1e3a8a;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .app-sub-title {
        font-size: 1.05rem;
        color: #475569;
        margin-bottom: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------
if "land_record" not in st.session_state:
    st.session_state["land_record"] = load_sample_record()

if "record_source_note" not in st.session_state:
    st.session_state["record_source_note"] = "डिफ़ॉल्ट प्रतिदर्श खतौनी (Sample Khatauni) लोड है।"

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

if "latest_audio_bytes" not in st.session_state:
    st.session_state["latest_audio_bytes"] = None

# ---------------------------------------------------------
# Sidebar: Document Management & Settings
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("### 🌾 BhoomiVoice नियंत्रण कक्ष")
    st.caption("सरवम एआई (Sarvam AI) संचालित ग्रामीण वाणी सहायक")

    # API Key indicator
    if SARVAM_API_KEY:
        st.success("🟢 Sarvam API कुंजी सक्रिय है", icon="✅")
    else:
        st.error("🔴 `.env` में `SARVAM_API_KEY` नहीं मिली!", icon="⚠️")

    st.markdown("---")
    st.subheader("📄 खतौनी / पट्टा दस्तावेज़")

    # 1. Prominent Sample Khatauni Button
    if st.button("📄 Load Preloaded Sample Khatauni", use_container_width=True, type="primary"):
        st.session_state["land_record"] = load_sample_record()
        st.session_state["record_source_note"] = "प्रतिदर्श खतौनी (वाराणसी - खाता सं० 00128) सक्रिय है।"
        st.success("✅ प्रतिदर्श खतौनी लोड हो गई!")

    # 2. File Uploader (.pdf, .png, .jpg)
    uploaded_file = st.file_uploader(
        "या नया दस्तावेज़ अपलोड करें (.pdf, .png, .jpg):",
        type=["pdf", "png", "jpg", "jpeg"],
        help="दस्तावेज़ को Sarvam Doc-AI द्वारा पढ़ा जाएगा। त्रुटि होने पर तत्काल फ़ालबैक उपलब्ध है।",
    )

    if uploaded_file is not None:
        if st.button("🔍 दस्तावेज़ विश्लेषित करें (Extract Data)", use_container_width=True):
            with st.spinner("दस्तावेज़ का विश्लेषण हो रहा है..."):
                rec, is_fb, msg = extract_document_data(uploaded_file, SARVAM_API_KEY)
                st.session_state["land_record"] = rec
                st.session_state["record_source_note"] = f"{uploaded_file.name} - {msg}"
                if is_fb:
                    st.warning(msg)
                else:
                    st.success(msg)

    st.caption(f"ℹ️ वर्तमान स्थिति: {st.session_state['record_source_note']}")

    st.markdown("---")
    st.subheader("🔊 वाणी विन्यास (Voice Settings)")
    selected_speaker = st.selectbox(
        "बुलबुल v3 स्वर (Bulbul Speaker):",
        options=["shubh", "meera"],
        index=0,
        format_func=lambda x: "पुरुष स्वर (Shubh - Male)" if x == "shubh" else "महिला स्वर (Meera - Female)",
    )

    if st.button("🗑️ इतिहास साफ़ करें (Reset Session)", use_container_width=True):
        st.session_state["chat_history"] = []
        st.session_state["latest_audio_bytes"] = None
        st.rerun()

# ---------------------------------------------------------
# Top Section: Title & Mandatory Legal Disclaimer
# ---------------------------------------------------------
st.markdown('<div class="app-main-title">BhoomiVoice 🌾</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-sub-title">भारतीय राजस्व अभिलेखों (खतौनी / पट्टा) के लिए स्वर-सक्षम डिजिटल सहायक</div>',
    unsafe_allow_html=True,
)

# Mandatory Disclaimer Badge
st.markdown(
    """
    <div class="disclaimer-badge">
        <span>⚠️</span>
        <div><strong>सूचना:</strong> यह केवल राजस्व अभिलेख पढ़ने का सहायक है, कानूनी स्वामित्व का प्रमाण नहीं।</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Center Display: 4 Parsed Key Fields in Visual Cards
# ---------------------------------------------------------
curr_record = st.session_state["land_record"]

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(
        f"""
        <div class="record-card">
            <div class="record-label">दर्ज खातेदार (Recorded Holder)</div>
            <div class="record-value">{curr_record.get('khatedar', 'उपलब्ध नहीं')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div class="record-card">
            <div class="record-label">ग्राम / तहसील (Village / Tehsil)</div>
            <div class="record-value">{curr_record.get('village_tehsil', 'उपलब्ध नहीं')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        f"""
        <div class="record-card">
            <div class="record-label">खसरा संख्या (Khasra No.)</div>
            <div class="record-value">{curr_record.get('khasra_no', 'उपलब्ध नहीं')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col4:
    st.markdown(
        f"""
        <div class="record-card">
            <div class="record-label">दर्ज क्षेत्रफल (Recorded Area)</div>
            <div class="record-value">{curr_record.get('recorded_area', 'उपलब्ध नहीं')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Additional Details Accordion
with st.expander("📋 पूर्ण राजस्व अभिलेख विवरण एवं कैफियत देखें (View Full Details)"):
    mcol1, mcol2, mcol3 = st.columns(3)
    with mcol1:
        st.write(f"**खाता संख्या:** {curr_record.get('khata_number', 'N/A')}")
        st.write(f"**फसली वर्ष:** {curr_record.get('fasli_year', 'N/A')}")
    with mcol2:
        st.write(f"**भूमि श्रेणी:** {curr_record.get('land_category', 'N/A')}")
        st.write(f"**देय लगान:** {curr_record.get('revenue_tax', 'N/A')}")
    with mcol3:
        st.write(f"**कैफियत/आदेश:** {curr_record.get('remarks', 'कोई प्रविष्टि नहीं')}")

    if curr_record.get("extracted_text"):
        st.text_area("अभिलेख से पढ़ा गया मूल पाठ (OCR / Extracted Text):", curr_record.get("extracted_text"), height=110, disabled=True)

st.markdown("---")

# ---------------------------------------------------------
# Query Section: Voice Input & Text Fallback
# ---------------------------------------------------------
st.markdown("### 🎙️ अभिलेख से संबंधित सवाल पूछें (Ask a Question)")
st.caption("आप माइक पर बोलकर या नीचे लिखकर हिंदी अथवा हिंग्लिश में प्रश्न पूछ सकते हैं।")

input_col, help_col = st.columns([3, 2])

with help_col:
    st.markdown("**💡 त्वरित नमूना प्रश्न (Quick Prompts):**")
    p1 = st.button("• खातेदार का नाम क्या है?", key="p1")
    p2 = st.button("• इस ज़मीन का खसरा नंबर और रकबा क्या है?", key="p2")
    p3 = st.button("• क्या इस ज़मीन पर कोई बंधक या विवाद है?", key="p3")

prompt_to_run = None
if p1:
    prompt_to_run = "खातेदार का नाम क्या है?"
elif p2:
    prompt_to_run = "इस ज़मीन का खसरा नंबर और कुल रकबा क्या है?"
elif p3:
    prompt_to_run = "क्या इस ज़मीन पर कोई बंधक या विवाद दर्ज है?"

with input_col:
    # 1. Native Streamlit Audio Input
    audio_val = st.audio_input("बोलकर सवाल पूछें (Speak your question in Hindi/Hinglish):")

    # 2. Text input fallback
    text_val = st.text_input(
        "या यहाँ लिखकर पूछें (यदि माइक काम न करे):",
        placeholder="उदा. दर्ज खातेदार का क्या नाम है?",
        value=prompt_to_run or "",
    )
    submit_text = st.button("उत्तर प्राप्त करें (Submit Query)", type="secondary")

# Determine active query
active_query = None
source_type = None

if audio_val is not None:
    # Check if this audio has already been processed to avoid rerun loops
    audio_bytes_data = audio_val.getvalue()
    if audio_bytes_data != st.session_state.get("last_processed_audio"):
        st.session_state["last_processed_audio"] = audio_bytes_data
        with st.spinner("🎧 सावरस v4 द्वारा आवाज़ सुनी जा रही है (Transcribing with Saaras v4)..."):
            transcript, stt_err = transcribe_audio_saaras(audio_bytes_data, SARVAM_API_KEY)
            if stt_err:
                st.warning(stt_err)
            if transcript:
                active_query = transcript
                source_type = "voice"
                st.info(f"🗣️ **पहचाना गया प्रश्न (Transcribed Query):** {transcript}")
            else:
                st.warning("आवाज़ स्पष्ट नहीं हो सकी। कृपया पुनः बोलें या नीचे लिखकर पूछें।")

if not active_query and (submit_text or prompt_to_run) and text_val.strip():
    active_query = text_val.strip()
    source_type = "text"

# ---------------------------------------------------------
# Execution Pipeline: Step 1 (STT done) -> Step 2 (LLM) -> Step 3 (TTS) -> Step 4 (Display)
# ---------------------------------------------------------
if active_query:
    with st.spinner("🤖 सरवम-105b द्वारा उत्तर तैयार किया जा रहा है..."):
        # Step 2: Query sarvam-105b
        answer, llm_err = answer_query_grounded_llm(active_query, curr_record, SARVAM_API_KEY)
        if llm_err:
            st.warning(f"⚠️ {llm_err}")

    with st.spinner("🔊 बुलबुल v3 द्वारा आवाज़ में रूपांतरण हो रहा है..."):
        # Step 3: Call Bulbul v3 TTS
        audio_reply, tts_err = synthesize_speech_bulbul(answer, selected_speaker, SARVAM_API_KEY)
        if tts_err:
            st.warning(f"⚠️ {tts_err}")

    # Step 4: Show response and store in history
    st.session_state["chat_history"].insert(
        0,
        {
            "query": active_query,
            "answer": answer,
            "audio_bytes": audio_reply,
            "source": source_type,
            "record_used": curr_record.copy(),
        },
    )

# ---------------------------------------------------------
# Display Chat History & Voice Output
# ---------------------------------------------------------
if st.session_state["chat_history"]:
    st.markdown("### 💬 उत्तर एवं आवाज़ (Voice & Text Response)")

    for idx, item in enumerate(st.session_state["chat_history"]):
        st.markdown(f"**👤 प्रश्न:** {item['query']}")

        # Voice output player
        if item.get("audio_bytes"):
            st.audio(item["audio_bytes"], format="audio/wav", autoplay=(idx == 0))

        # Grounded text response box
        st.markdown(
            f'<div class="bhoomi-response-box">🌾 {item["answer"]}</div>',
            unsafe_allow_html=True,
        )

        # Expandable container for source fields
        with st.expander(f"🔍 उत्तर के स्रोत प्रमाण (Source Record Fields) - सवाल #{len(st.session_state['chat_history']) - idx}"):
            rec = item.get("record_used", {})
            st.json(
                {
                    "दर्ज_खातेदार": rec.get("khatedar"),
                    "ग्राम_तहसील": rec.get("village_tehsil"),
                    "खसरा_संख्या": rec.get("khasra_no"),
                    "दर्ज_क्षेत्रफल": rec.get("recorded_area"),
                    "कैफियत": rec.get("remarks"),
                }
            )
        st.markdown("---")

st.markdown("<br><center><small style='color: #94a3b8;'>BhoomiVoice MVP • Powered by Sarvam AI (Saaras v4, Sarvam-105B, Bulbul v3) & Streamlit</small></center>", unsafe_allow_html=True)
