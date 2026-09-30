import os

import azure.cognitiveservices.speech as speechsdk
from azure.ai.translation.text import TextTranslationClient
from azure.core.credentials import AzureKeyCredential
import streamlit as st

# Make the header of the app more compact by removing the default menu and footer.
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

#Configure the browser tab and keep the page content centered.Can you add some emojis or icons to the page title and favicon to make it more visually appealing

st.set_page_config(page_title="Read It Out Loud", page_icon="🔊", layout="centered")


# Read a setting from Streamlit secrets first, then fall back to environment variables.
def get_setting(name: str) -> str:
    try:
        value = st.secrets.get(name)
    except Exception:
        # Streamlit secrets may be unavailable when the app has no secrets file.
        value = None
    return value or os.getenv(name, "")


# Fetch and format the voices offered by this Azure Speech resource.
# Cache the result for one hour to avoid repeating the network request on each rerun.
@st.cache_data(ttl=3600, show_spinner=False)
def get_available_voices(speech_key: str, speech_region: str) -> list[dict[str, str]]:
    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key,
        region=speech_region,
    )
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=None,
    )
    result = synthesizer.get_voices_async().get()

    # Keep the fields needed by the dropdown and sort voices by language and name.
    return sorted(
        [
            {
                "name": voice.short_name,
                "locale": voice.locale,
                "local_name": voice.local_name,
                "gender": str(voice.gender).split(".")[-1],
            }
            for voice in result.voices
        ],
        key=lambda voice: (voice["locale"], voice["name"]),
    )


# Translate the submitted text into English; Translator detects its source language.
def translate_to_english(
    translator_key: str,
    translator_region: str,
    translator_endpoint: str,
    text: str,
) -> tuple[str, str]:
    credential = AzureKeyCredential(translator_key)
    client = TextTranslationClient(
        endpoint=translator_endpoint,
        credential=credential,
        region=translator_region,
    )
    try:
        response = client.translate(
            body=[text],
            to_language=["en"],
        )
        if not response or not response[0].translations:
            raise RuntimeError("The Translator service returned no translated text.")

        translated_text = response[0].translations[0].text
        detected_language = response[0].detected_language
        source_language = detected_language.language if detected_language else "unknown"
        return translated_text, source_language
    finally:
        client.close()


# Convert the supplied text to WAV audio using the selected Azure voice.
def synthesize_speech(speech_key: str, speech_region: str, voice_name: str, text: str) -> bytes:
    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key,
        region=speech_region,
    )
    # Select the requested voice and a WAV-compatible audio format.
    speech_config.speech_synthesis_voice_name = voice_name
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
    )
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=None,
    )
    result = synthesizer.speak_text_async(text).get()

    # Return audio bytes on success; surface Azure's cancellation details on failure.
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return result.audio_data

    details = result.cancellation_details
    message = details.error_details or str(details.reason)
    raise RuntimeError(message)


# Display the app heading and a brief explanation of its purpose.
st.title("Read it out loud")
st.write("Translate text to English, then listen with Azure AI Speech.")

# Load Azure service credentials and stop early when any required setting is missing.
speech_key = get_setting("SPEECH_KEY")
speech_region = get_setting("SPEECH_REGION")
translator_key = get_setting("TRANSLATOR_KEY")
translator_region = get_setting("TRANSLATOR_REGION")
translator_endpoint = get_setting("TRANSLATOR_ENDPOINT")

if not speech_key or not speech_region:
    st.info(
        "Set `SPEECH_KEY` and `SPEECH_REGION` in Streamlit secrets or as environment variables to get started."
    )
    st.stop()

# Translation requires a Translator resource in addition to the Speech resource.
if not translator_key or not translator_region or not translator_endpoint:
    st.info(
        "Set `TRANSLATOR_KEY`, `TRANSLATOR_REGION`, and `TRANSLATOR_ENDPOINT` "
        "in Streamlit secrets or as environment variables to enable translation."
    )
    st.stop()

# Ask Azure for the available voices and show a readable error if that request fails.
try:
    with st.spinner("Loading available voices..."):
        voices = get_available_voices(speech_key, speech_region)
except Exception as error:
    st.error(f"Couldn't load voices from Azure AI Speech: {error}")
    st.stop()

# Do not render the form if the Speech resource returned no voices.
if not voices:
    st.warning("No voices were returned for this Speech resource and region.")
    st.stop()


# Show each voice's localized name, language, and gender in the dropdown.
def format_voice(voice_name: str) -> str:
    voice = next(item for item in voices if item["name"] == voice_name)
    return f"{voice['local_name']} · {voice['locale']} · {voice['gender']}"


# Collect the source text and selected voice; translation runs when the form is submitted.
with st.form("speech_form"):
    text = st.text_area(
        "Text to translate and speak",
        placeholder="Type or paste something here...",
        height=220,
    )
    selected_voice = st.selectbox(
        "Voice",
        options=[voice["name"] for voice in voices],
        format_func=format_voice,
    )
    submitted = st.form_submit_button("Generate speech", type="primary")

# Translate valid input to English, show the translation, and synthesize that result.
if submitted:
    if not text.strip():
        st.warning("Enter some text before generating speech.")
    else:
        try:
            with st.spinner("Translating text to English..."):
                translated_text, source_language = translate_to_english(
                    translator_key,
                    translator_region,
                    translator_endpoint,
                    text.strip(),
                )

            st.subheader("English translation")
            st.caption(f"Detected source language: {source_language}")
            st.write(translated_text)

            with st.spinner("Generating speech..."):
                audio = synthesize_speech(
                    speech_key,
                    speech_region,
                    selected_voice,
                    translated_text,
                )
            st.audio(audio, format="audio/wav")
        except Exception as error:
            st.error(f"Translation or speech synthesis failed: {error}")