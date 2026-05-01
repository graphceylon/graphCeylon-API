"""
Sinhala TTS using the local fine-tuned VITS model (Coqui TTS).

The model was trained on Sinhala speech and produces WAV audio at 22 050 Hz.
Google Cloud TTS is NOT used for Sinhala — this module replaces it entirely.

Model files are located via environment variables (see config.py):
  SINHALA_TTS_MODEL_PATH  — path to sinhala_tts_model.pth
  SINHALA_TTS_CONFIG_PATH — path to config.json

The Synthesizer is loaded once and kept as a singleton; a threading.Lock
serialises concurrent requests so synthesis is always thread-safe.
"""

from __future__ import annotations

import io
import logging
import threading

import numpy as np
import scipy.io.wavfile

from .config import SINHALA_TTS_CONFIG_PATH, SINHALA_TTS_MODEL_PATH

logger = logging.getLogger(__name__)

# Sample rate defined in the model's config.json audio.sample_rate
SAMPLE_RATE = 22_050

_synthesizer = None
_lock = threading.Lock()


def _get_synthesizer():
    """Lazy-load the Coqui TTS Synthesizer singleton (expensive — model weights)."""
    global _synthesizer
    if _synthesizer is None:
        from TTS.utils.synthesizer import Synthesizer  # type: ignore[import]

        logger.info(
            "Loading Sinhala VITS model: model=%s, config=%s",
            SINHALA_TTS_MODEL_PATH,
            SINHALA_TTS_CONFIG_PATH,
        )
        _synthesizer = Synthesizer(
            tts_checkpoint=SINHALA_TTS_MODEL_PATH,
            tts_config_path=SINHALA_TTS_CONFIG_PATH,
        )
        logger.info("Sinhala VITS model loaded (sample_rate=%d Hz)", SAMPLE_RATE)
    return _synthesizer


def synthesize_sinhala(text: str) -> bytes:
    """
    Synthesize Sinhala text using the local VITS model.

    Args:
        text: Sinhala text to synthesize.

    Returns:
        WAV audio bytes (PCM16, 22 050 Hz, mono).

    Raises:
        ValueError: If text is empty.
        RuntimeError: If the model files are missing or inference fails.
    """
    if not text or not text.strip():
        raise ValueError("Text for Sinhala TTS cannot be empty.")

    with _lock:
        syn = _get_synthesizer()
        logger.info("Synthesizing Sinhala text (%d chars): %r", len(text), text[:60])
        samples = syn.tts(text)

    # Convert float32 samples → int16 → WAV bytes in memory
    arr = np.array(samples, dtype=np.float32)
    arr = np.clip(arr, -1.0, 1.0)
    arr_int16 = (arr * 32_767).astype(np.int16)

    buf = io.BytesIO()
    scipy.io.wavfile.write(buf, SAMPLE_RATE, arr_int16)
    wav_bytes = buf.getvalue()

    logger.info("Sinhala TTS produced %d bytes of WAV audio", len(wav_bytes))
    return wav_bytes
