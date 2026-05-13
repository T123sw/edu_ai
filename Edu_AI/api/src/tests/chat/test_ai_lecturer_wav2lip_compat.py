from pathlib import Path
import sys


def test_wav2lip_mel_basis_supports_current_librosa():
    wav2lip_dir = Path(__file__).resolve().parents[2] / "AI_Lecturer" / "Wav2Lip_Offline"
    sys.path.insert(0, str(wav2lip_dir))
    try:
        import audio
        from hparams import hparams as hp

        audio._mel_basis = None
        mel_basis = audio._build_mel_basis()

        assert mel_basis.shape[0] == hp.num_mels
        assert mel_basis.shape[1] == hp.n_fft // 2 + 1
    finally:
        try:
            sys.path.remove(str(wav2lip_dir))
        except ValueError:
            pass
