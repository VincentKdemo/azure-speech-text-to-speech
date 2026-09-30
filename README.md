# Azure AI Speech Text-to-Speech

A small Streamlit app that translates submitted text into English with Azure AI Translator, then reads the translation aloud with a selectable Azure AI Speech voice.

## Setup

1. Create or activate a Python virtual environment.
2. Install the dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Configure both Azure resources. Add these values to `.streamlit/secrets.toml` or set them as environment variables:

   ```toml
   SPEECH_KEY = "your-speech-resource-key"
   SPEECH_REGION = "your-speech-resource-region"
   TRANSLATOR_KEY = "your-translator-resource-key"
   TRANSLATOR_REGION = "your-translator-resource-region"
   TRANSLATOR_ENDPOINT = "your-translator-resource-endpoint"
   ```
4. Start the app:

   ```powershell
   streamlit run app.py
   ```

The voice menu is retrieved from Azure when the app starts and cached for one hour. Submitted text is auto-detected and translated to English before speech synthesis. The translation is shown on the page, and audio is synthesized as WAV data for playback in Streamlit.
