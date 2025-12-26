# handle_text_input(session_id, text)
# handle_voice_input(session_id, base64_audio)
# steps: STT(if voice) → normalize → detect_lang → translate_to_en → save(session lang+mode) → build JSON → send orchestrator

