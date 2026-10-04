from src.overlay.clickthrough import click_through_targets


class Window:
    pass


def test_control_center_is_never_a_click_through_target():
    control = Window()
    coach = Window()
    driver = Window()
    replay = Window()
    targets = click_through_targets((control, coach, driver, replay), control)
    assert targets == (coach, driver, replay)
    assert control not in targets
