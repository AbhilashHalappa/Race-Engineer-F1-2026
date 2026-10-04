from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_single_markdown_documentation_file():
    docs = sorted(
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob("*.md")
        if ".pytest_cache" not in p.parts
    )
    assert docs == ["RACE_ENGINEER_STABLE_V2.md"]


def test_release_build_copies_single_documentation_file():
    build = (ROOT / "build_exe.ps1").read_text(encoding="utf-8")
    assert "RACE_ENGINEER_STABLE_V2.md" in build
    assert "FIRST_RUN.md" not in build
    assert "RADIO_COMMAND_REFERENCE.md" not in build


def test_obsolete_root_artifacts_removed():
    forbidden = [
        "snippet.txt", "full_pytest_before.txt", "build_exe_legacy_pyinstaller_REFERENCE.ps1",
        "STABLE_V2_FULL_REGRESSION.txt", "STABLE_V2_RC2_FULL_REGRESSION.txt",
    ]
    for name in forbidden:
        assert not (ROOT / name).exists(), name
    assert not list(ROOT.glob("RUN_RACE_ENGINEER_V*.bat"))


def test_active_release_inputs_remain():
    for name in ["requirements.txt", "runtime_dependencies.json", "V2_SOURCE_FREEZE_MANIFEST.json"]:
        assert (ROOT / name).is_file(), name
