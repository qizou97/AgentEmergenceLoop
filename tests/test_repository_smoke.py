from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_required_harness_files_exist() -> None:
    required = [
        "AGENTS.md",
        "feature_list.json",
        "progress.md",
        "init.sh",
    ]

    missing = [name for name in required if not (ROOT / name).exists()]
    assert not missing, f"missing required harness files: {missing}"

