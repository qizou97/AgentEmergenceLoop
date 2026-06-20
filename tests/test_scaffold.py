"""
test_scaffold.py — project tree + fixed run_benchmark.py template (spec §9).

scaffold writes the directory skeleton an agent fills in, plus a fixed
run_benchmark.py the agent must never edit. The template is a thin entrypoint:
it loads frozen contracts and calls sobench.runner.run — no method logic.
"""

from __future__ import annotations

from sobench.scaffold import scaffold


def test_scaffold_creates_tree(tmp_path):
    proj = tmp_path / "spatial_domain_identification"
    scaffold(proj, "spatial_domain_identification")

    assert proj.is_dir()
    assert (proj / "methods").is_dir()
    assert (proj / "results").is_dir()
    assert (proj / "run_benchmark.py").is_file()


def test_run_benchmark_template_compiles(tmp_path):
    proj = tmp_path / "p"
    scaffold(proj, "spatial_domain_identification")
    src = (proj / "run_benchmark.py").read_text()
    compile(src, str(proj / "run_benchmark.py"), "exec")  # raises SyntaxError if broken


def test_run_benchmark_calls_runner(tmp_path):
    proj = tmp_path / "p"
    scaffold(proj, "spatial_domain_identification")
    src = (proj / "run_benchmark.py").read_text()
    assert "sobench.runner" in src
    assert "run(" in src


def test_run_benchmark_has_no_method_logic(tmp_path):
    """The template must be method-agnostic — no hardcoded method names."""
    proj = tmp_path / "p"
    scaffold(proj, "spatial_domain_identification")
    src = (proj / "run_benchmark.py").read_text()
    for method in ("STAGATE", "MENDER", "SpaGCN"):
        assert method not in src


def test_scaffold_is_idempotent(tmp_path):
    proj = tmp_path / "p"
    scaffold(proj, "spatial_domain_identification")
    scaffold(proj, "spatial_domain_identification")  # second call must not raise
    assert (proj / "run_benchmark.py").is_file()
