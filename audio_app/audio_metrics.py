"""Audio metric extraction — strict lane separation per ADR 0001.

pydub owns duration_sec, sample_rate_hz, bitrate_kbps.
librosa owns loudness_db only, via frame-based RMS -> dB (not pydub's whole-file dBFS).
No metric is computed by both libraries.
"""
import numpy as np
from pydub import AudioSegment
import librosa


def extract_pydub_metrics(path):
    segment = AudioSegment.from_file(path)
    duration_sec = len(segment) / 1000.0
    sample_rate_hz = segment.frame_rate
    # Bitrate computed as the decoded PCM bitrate (sample_rate x bit_depth x channels),
    # not the original container's encoded bitrate — pydub doesn't expose the latter
    # directly, and this keeps the calculation identical and defensible across formats
    # (WAV has no native bitrate metadata field at all, per ADR 0001).
    bits_per_sample = segment.sample_width * 8
    bitrate_kbps = (sample_rate_hz * bits_per_sample * segment.channels) / 1000.0
    return duration_sec, sample_rate_hz, bitrate_kbps


def extract_loudness_db(path):
    y, _sr = librosa.load(path, sr=None, mono=True)
    rms = librosa.feature.rms(y=y)[0]
    db = librosa.amplitude_to_db(rms, ref=1.0)
    return float(np.mean(db))


def extract_all_metrics(path):
    duration_sec, sample_rate_hz, bitrate_kbps = extract_pydub_metrics(path)
    loudness_db = extract_loudness_db(path)
    return {
        "duration_sec": round(duration_sec, 3),
        "sample_rate_hz": sample_rate_hz,
        "bitrate_kbps": round(bitrate_kbps, 1),
        "loudness_db": round(loudness_db, 2),
    }
