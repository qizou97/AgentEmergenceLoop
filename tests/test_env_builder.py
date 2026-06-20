"""
test_env_builder.py — pure, deterministic helpers (spec §3 `env`).

Real conda env creation (mamba/conda) is exercised only by the opt-in
integration test. Here we test the deterministic pieces: env.yml hashing and the
"is this env_record current for this env.yml?" check. env.yml content mirrors the
real STAGATE_pyG requirement.txt so the fixture stays task-derived.
"""

from __future__ import annotations

from sobench.atomicio import write_json_atomic
from sobench.env_builder import env_record_is_current, env_yml_hash

# Derived from data/.../codes/STAGATE_pyG/requirement.txt (real method deps).
STAGATE_ENV_YML = """\
name: sobench_STAGATE_pyG
channels:
  - conda-forge
dependencies:
  - python=3.9
  - pip
  - pip:
      - scanpy>=1.6.1
      - scikit-learn>=0.23.2
"""


def test_env_yml_hash_is_stable_and_sensitive(tmp_path):
    a = tmp_path / "a.yml"
    a.write_text(STAGATE_ENV_YML)
    h1 = env_yml_hash(a)
    h2 = env_yml_hash(a)
    assert h1 == h2
    assert h1.startswith("sha256:")

    b = tmp_path / "b.yml"
    b.write_text(STAGATE_ENV_YML + "      - tqdm\n")
    assert env_yml_hash(b) != h1


def test_env_record_is_current_true_when_hash_matches(tmp_path):
    env_yml = tmp_path / "env.yml"
    env_yml.write_text(STAGATE_ENV_YML)
    rec = tmp_path / "env_record.json"
    write_json_atomic(rec, {"env_yml_hash": env_yml_hash(env_yml),
                            "interpreter_path": "/x/bin/python"})
    assert env_record_is_current(rec, env_yml) is True


def test_env_record_is_current_false_when_hash_differs(tmp_path):
    env_yml = tmp_path / "env.yml"
    env_yml.write_text(STAGATE_ENV_YML)
    rec = tmp_path / "env_record.json"
    write_json_atomic(rec, {"env_yml_hash": "sha256:stale", "interpreter_path": "/x/bin/python"})
    assert env_record_is_current(rec, env_yml) is False


def test_env_record_is_current_false_when_record_absent(tmp_path):
    env_yml = tmp_path / "env.yml"
    env_yml.write_text(STAGATE_ENV_YML)
    assert env_record_is_current(tmp_path / "nope.json", env_yml) is False
