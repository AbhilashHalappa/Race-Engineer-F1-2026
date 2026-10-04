from src.corner_coach import CornerCoachEngine
from src.corner_coach_models import CoachingZone, Diagnosis


def test_live_corner_publish_uses_diagnosis_phase_losses_s_contract():
    engine = object.__new__(CornerCoachEngine)
    engine._v202_accumulator = type("Accumulator", (), {"add_corner": lambda self, result: None})()
    zone = CoachingZone(
        zone_id="Z1", start_m=100.0, end_m=180.0, approach_start_m=40.0,
        corner_ids=(1,), label="T1"
    )
    diag = Diagnosis(
        zone_id="Z1", public_label="T1", net_loss_s=0.18,
        primary_code="brake_early", primary_text="brake early",
        confidence=0.9,
        measurements={"brake_point_delta_m": -12.0},
        phase_losses_s={"approach": 0.03, "entry": 0.10, "exit": 0.05},
    )

    engine._publish_v201_corner_result(zone, diag, 12.5)

    assert engine._live_corner_result["phase_losses"] == {
        "approach": 0.03, "entry": 0.10, "exit": 0.05
    }
