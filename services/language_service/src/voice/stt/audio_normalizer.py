from __future__ import annotations

import subprocess
import tempfile
import os
from pathlib import Path
from typing import Union


class AudioNormalizer:
    """
    Converts ANY audio format into:
      WAV / PCM 16-bit / 16kHz / Mono
    using system ffmpeg.
    """

    @staticmethod
    def normalize(
        input_path: Union[str, Path],
        *,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> Path:
        input_path = Path(input_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Audio file not found: {input_path}")

        out_fd, out_path = tempfile.mkstemp(suffix=".wav")
        os.close(out_fd)
        out_path = Path(out_path)

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-ac", str(channels),
            "-ar", str(sample_rate),
            "-f", "wav",
            str(out_path),
        ]

        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError("FFmpeg audio normalization failed") from e

        return out_path
