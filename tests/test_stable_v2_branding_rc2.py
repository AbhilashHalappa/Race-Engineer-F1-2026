from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]


def test_brand_assets_are_release_ready():
    brand=ROOT/'assets'/'brand'
    required=[
        'race_engineer.ico','race_engineer_icon_96.png',
        'installer_wizard.bmp','installer_small.bmp',
    ]
    for name in required:
        p=brand/name
        assert p.is_file() and p.stat().st_size > 100, name


def test_qt_runtime_uses_shared_branding():
    runtime=(ROOT/'src'/'overlay'/'runtime.py').read_text(encoding='utf-8')
    branding=(ROOT/'src'/'branding.py').read_text(encoding='utf-8')
    window=(ROOT/'src'/'overlay'/'window.py').read_text(encoding='utf-8')
    assert 'configure_qt_application(app)' in runtime
    assert 'race_engineer.ico' in branding
    assert 'RACE ENGINEER' in window and 'STABLE V2' in window
    assert 'TELEMETRY  •  STRATEGY  •  COACHING' in window
    assert 'AI Race Engineer - Control Center' not in window


def test_portable_build_copies_brand_assets_and_winres_hook():
    build=(ROOT/'build_exe.ps1').read_text(encoding='utf-8')
    assert "Copy-Item '.\\assets'" in build
    assert 'go-winres' in build
    assert 'race_engineer.ico' in build


def test_installer_is_branded():
    iss=(ROOT/'installer'/'RaceEngineer.iss').read_text(encoding='utf-8')
    assert 'SetupIconFile=..\\assets\\brand\\race_engineer.ico' in iss
    assert 'WizardImageFile=..\\assets\\brand\\installer_wizard.bmp' in iss
    assert 'WizardSmallImageFile=..\\assets\\brand\\installer_small.bmp' in iss
    assert 'IconFilename: "{app}\\assets\\brand\\race_engineer.ico"' in iss


def test_dependency_policy_is_unchanged_and_rc2_labelled():
    cfg=json.loads((ROOT/'runtime_dependencies.json').read_text(encoding='utf-8'))
    assert cfg['release'].startswith('Stable V2 RC3')
    assert 'not embedded' in cfg['policy']
    assert cfg['llm']['runtime']=='Ollama'
    assert cfg['stt']['model_name']=='small.en'
