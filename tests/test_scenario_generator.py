from sentinel_alpha.research.scenario_generator import ScenarioGenerator


def test_pressure_scenario_contains_narrative_and_truth() -> None:
    package = ScenarioGenerator(seed=3).generate("drawdown", cohort="pressure")

    assert package.playbook == "drawdown"
    assert package.cohort == "pressure"
    assert len(package.price_track) == 20
    assert len(package.narrative_track) == 20
    assert len(package.truth_track) == 20
    assert package.price_track[-1].drawdown_pct < 0


def test_control_scenario_omits_narrative_track() -> None:
    package = ScenarioGenerator(seed=3).generate("oscillation", cohort="control")

    assert package.cohort == "control"
    assert len(package.price_track) == 16
    assert package.narrative_track == []


def test_fake_reversal_assessment_flags_bottom_fishing() -> None:
    generator = ScenarioGenerator(seed=3)
    package = generator.generate("fake_reversal", cohort="pressure")
    assessment = generator.assess_fake_reversal(
        package,
        buy_actions=3,
        total_actions=4,
        user_sentiment_score=0.9,
    )

    assert package.playbook == "fake_reversal"
    assert assessment.deception_score > 0.5
    assert assessment.premature_bottom_fishing is True
