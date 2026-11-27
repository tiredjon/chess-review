"""Фундамент сессии 17: ключи уроков и формат файлов эталонов."""

from app.coach.lessons import LESSONS, METRIC_LESSONS, lesson_for
from app.coach.norms_data import load_norms, load_trajectories, parse_norms, parse_trajectories


def test_every_metric_has_a_known_lesson() -> None:
    assert set(METRIC_LESSONS.values()) <= set(LESSONS)
    assert lesson_for("motif", "fork") == "fork"
    assert lesson_for("motif", "unknown") is None
    assert lesson_for("opening", "white:Italian Game") == "opening_repertoire"


def test_shipped_files_parse() -> None:
    assert load_norms().version
    assert load_trajectories().version


def test_norms_format_and_nearest_band() -> None:
    norms = parse_norms(
        {
            "version": "t",
            "time_classes": {
                "rapid": {
                    "bands": [
                        {
                            "center": c,
                            "lo": c - 100,
                            "hi": c + 100,
                            "players": 1,
                            "games": 1,
                            "moves": 40,
                            "metrics": {"accuracy": {"p25": 1, "p50": 2, "p75": 3, "n": 1}},
                        }
                        for c in (2000, 1800)
                    ]
                }
            },
        }
    )
    band = norms.nearest("rapid", 1760)
    assert band is not None
    assert band.center == 1800
    assert band.metrics["accuracy"].p50 == 2
    assert norms.nearest("blitz", 1760) is None


def test_trajectories_format() -> None:
    tr = parse_trajectories(
        {
            "version": "t",
            "time_classes": {
                "rapid": {
                    "rows": [
                        {
                            "from_center": 1700,
                            "gain": 300,
                            "players": 10,
                            "reached_52w": 0.1,
                            "reached_104w": 0.2,
                            "reached_156w": 0.3,
                            "weeks_p25": 40,
                            "weeks_p50": 70,
                            "weeks_p75": None,
                            "activity": [
                                {
                                    "games_per_week_lo": 0,
                                    "games_per_week_hi": 3,
                                    "players": 4,
                                    "reached_104w": 0.1,
                                    "weeks_p50": None,
                                }
                            ],
                        }
                    ]
                }
            },
        }
    )
    row = tr.nearest("rapid", 1720, 280)
    assert row is not None
    assert row.weeks_p75 is None
    assert row.activity[0].players == 4
