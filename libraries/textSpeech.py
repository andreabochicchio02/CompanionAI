import sounddevice as sd
import scipy.io.wavfile as wavfile
import whisper
import torch
import os
import numpy as np
from TTS.api import TTS

import logging
logging.getLogger().setLevel(logging.ERROR)

device = "cuda" if torch.cuda.is_available() else "cpu"

# Load the Whisper model (available options: tiny, base, small, medium, large)
speech_to_text_model = whisper.load_model("base")

text_to_speech_tts = TTS("tts_models/en/ljspeech/fast_pitch").to(device)

def speech_to_text_locally():
    fs = 16000  # sample rate in Hz
    seconds = 5  # recording duration in seconds

    # Record audio from the microphone
    recording = sd.rec(int(seconds * fs), samplerate=fs, channels=1)
    sd.wait()

    # Save the recording to a WAV file
    wavfile.write("input.wav", fs, recording)

    # Transcribe the recorded audio file
    result = speech_to_text_model.transcribe("input.wav")

    # Remove the audio file after transcription
    os.remove("input.wav")

    return result["text"]

def text_to_speech_locally(text):
    wav = text_to_speech_tts.tts(text=text)
    wav = wav / np.max(np.abs(wav))
    # Play the generated audio
    sd.play(wav, samplerate=text_to_speech_tts.synthesizer.output_sample_rate)
    sd.wait()