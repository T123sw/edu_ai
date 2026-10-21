"""Compatibility import for historical extensions; active callers use SpeechService."""
from .tts_service import SpeechService
OpenMaicTtsService = SpeechService
