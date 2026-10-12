"""Transcricao de voz (decisao 26): Whisper local na VPS, via faster-whisper.

O mascote grava PCM 16 bits, mono, 16 kHz, e manda para POST /api/voz. Aqui o audio
vira texto. O modelo carrega na primeira fala (demora alguns segundos) e fica na memoria.

Instalar (fora do sistema, por causa do PEP 668):
    python3 -m venv ~/.local/share/mascote/venv
    ~/.local/share/mascote/venv/bin/pip install faster-whisper
e rodar a ponte com ~/.local/share/mascote/venv/bin/python3 (ver README.md).

Config (~/.config/mascote/ponte.json): stt_modelo ("small"), stt_idioma ("pt"),
stt_threads (0 = automatico), stt_dispositivo ("cpu"), stt_compute ("int8").
"""
import array
import threading

TAXA = 16000
MIN_AMOSTRAS = TAXA // 4          # menos de 0,25 s: nao transcreve
MAX_SEGUNDOS = 30


class SemTranscritor(RuntimeError):
    """faster-whisper nao instalado ou modelo indisponivel."""


def pcm_para_float(pcm):
    """bytes PCM s16le -> lista de floats em -1..1 (sem numpy, para os testes)."""
    a = array.array('h')
    a.frombytes(pcm[:len(pcm) // 2 * 2])
    return [x / 32768.0 for x in a]


class Transcritor:
    def __init__(self, cfg=None):
        cfg = cfg or {}
        self.modelo_nome = cfg.get('stt_modelo', 'small')
        self.idioma = cfg.get('stt_idioma', 'pt')
        self.threads = int(cfg.get('stt_threads', 0))
        self.dispositivo = cfg.get('stt_dispositivo', 'cpu')
        self.compute = cfg.get('stt_compute', 'int8')
        self._modelo = None
        self._trava = threading.Lock()   # um audio por vez: o modelo usa toda a CPU

    def _carregar(self):
        if self._modelo is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise SemTranscritor('faster-whisper nao instalado (ver stt.py)') from e
            self._modelo = WhisperModel(self.modelo_nome, device=self.dispositivo, compute_type=self.compute,
                                        cpu_threads=self.threads)
        return self._modelo

    def transcrever(self, pcm):
        if len(pcm) // 2 < MIN_AMOSTRAS:
            return ''
        pcm = pcm[:MAX_SEGUNDOS * TAXA * 2]
        with self._trava:
            modelo = self._carregar()
            import numpy as np
            audio = np.frombuffer(pcm[:len(pcm) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768.0
            segmentos, _ = modelo.transcribe(audio, language=self.idioma, beam_size=1, vad_filter=True,
                                             condition_on_previous_text=False)
            return ' '.join(s.text.strip() for s in segmentos).strip()
