from pathlib import Path
import json
import struct

ROOT = Path(__file__).resolve().parents[1]


def test_stable_v2_launcher_is_small_windows_pe_not_model_bundle():
    exe = ROOT / "RaceEngineer.exe"
    assert exe.is_file()
    raw = exe.read_bytes()
    assert raw[:2] == b"MZ"
    pe_off = struct.unpack_from("<I", raw, 0x3C)[0]
    assert raw[pe_off:pe_off + 4] == b"PE\x00\x00"
    # Piper is ~64 MB, Whisper small.en ~486 MB, and the Ollama model is much
    # larger.  A <8 MB launcher proves those payloads are not embedded here.
    assert exe.stat().st_size < 8 * 1024 * 1024


def test_runtime_dependency_manifest_uses_external_official_model_sources():
    cfg = json.loads((ROOT / "runtime_dependencies.json").read_text(encoding="utf-8"))
    assert cfg["schema"] == 1
    assert cfg["python"]["required_major_minor"] == "3.13"
    assert cfg["python"]["download_url"].startswith("https://www.python.org/")
    assert cfg["piper_voice"]["model_url"].startswith("https://huggingface.co/rhasspy/piper-voices/")
    assert cfg["piper_voice"]["model_sha256"] == "0a309668932205e762801f1efc2736cd4b0120329622adf62be09e56339d3330"
    assert cfg["stt"]["repo_id"] == "Systran/faster-whisper-small.en"
    assert cfg["llm"]["runtime"] == "Ollama"
    assert cfg["llm"]["model"] == "qwen2.5:3b"
    assert cfg["llm"]["download_url"].startswith("https://ollama.com/")


def test_bootstrapper_checks_and_prompts_instead_of_bundling_dependencies():
    src = (ROOT / "launcher" / "bootstrapper_windows.go").read_text(encoding="utf-8")
    for token in [
        "ensureVenv",
        "ensurePythonPackages",
        "ensurePiperVoice",
        "ensureSTT",
        "ensureLLM",
        "snapshot_download",
        "ollama pull",
        "askYesNo",
        "--check-only",
        "--safe-mode",
        "bootstrapper_status.json",
    ]:
        assert token in src
    assert "PyInstaller" not in src


def test_stable_build_path_does_not_pyinstaller_bundle_runtime_dependencies():
    build = (ROOT / "build_exe.ps1").read_text(encoding="utf-8")
    assert "go.Source build" in build
    assert "bootstrapper_windows.go" in build
    assert "-m PyInstaller" not in build
    assert "No Python runtime, Piper voice, Whisper model, Ollama runtime or LLM model is embedded" in build


def test_large_model_payloads_are_not_shipped_in_source_release():
    # The source/full audit tree must not accidentally include downloaded model
    # binaries.  They belong to first-run dependency provisioning.
    assert not list((ROOT / "voices").glob("*.onnx")) if (ROOT / "voices").exists() else True
    assert not list(ROOT.rglob("model.bin"))


def test_runtime_cli_branding_matches_stable_v2_release():
    src = (ROOT / "src" / "main.py").read_text(encoding="utf-8")
    assert "Race Engineer Stable V2 / V2.0.0" in src
    assert "AI Race Engineer V1.8.0.0: Driving Performance Engine Completion" not in src
    assert "Start Race Engineer from this Stable V2 folder" in src


def test_installer_preserves_current_user_data_and_downloaded_voice_models():
    iss = (ROOT / "installer" / "RaceEngineer.iss").read_text(encoding="utf-8")
    assert "user_data\\*" in iss
    assert "voices\\*" in iss
    assert 'Name: "{app}\\user_data"' in iss
    assert 'Name: "{app}\\voices"' in iss


def test_build_stage_removes_python_bytecode_caches():
    build = (ROOT / "build_exe.ps1").read_text(encoding="utf-8")
    assert "__pycache__" in build
    assert "*.pyc" in build
