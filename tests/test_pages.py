"""Offline tests for the GitHub Pages publication step (no build, no network)."""
import gzip
import json
from pathlib import Path

from pipeline.pages import (
    APP_SITE,
    compact_bundle,
    compact_calculation_details,
    expand_calculation_details,
    site_config,
    site_for,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "calculation_details_compact.json")
                     .read_text(encoding="utf-8"))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def test_compact_format_is_pinned_by_the_shared_fixture():
    # app/tests/site.test.mjs expands the same fixture in TypeScript.
    assert compact_calculation_details(FIXTURE["expanded"]) == FIXTURE["compact"]


def test_compact_expands_back_exactly():
    expanded = FIXTURE["expanded"]
    restored = expand_calculation_details(compact_calculation_details(expanded))
    assert canonical(restored) == canonical(expanded)
    assert restored["20251231"] == {}                  # a year without entries survives
    assert "reason" not in restored["20241231"]["ccc"]  # per-year keys are not spread
    # 0 and 0.0 are different JSON values: never merged into one shared field
    assert type(restored["20231231"]["raw:revenue"]["value"]) is int
    assert type(restored["20241231"]["raw:revenue"]["value"]) is float


def test_uncompacted_index_passes_through():
    assert expand_calculation_details(FIXTURE["expanded"]) is FIXTURE["expanded"]


def test_bundles_split_by_exchange_on_one_origin():
    assert site_for("600519.SH") == APP_SITE
    assert site_for("430047.BJ") == APP_SITE
    assert site_for("000651.SZ") == "business-model-explorer-data"
    config = site_config()
    assert config["base"] == f"/{APP_SITE}/"
    assert config["bundleBases"] == {"SZ": "/business-model-explorer-data/data/"}


def test_compact_bundle_keeps_every_value(tmp_path):
    bundle = {"schema_version": 1, "ts_code": "000651.SZ", "unit": "CNY_yuan",
              "working_capital": [{"end_date": "20241231", "ccc": -35.4, "ccc_net_advances": None}],
              "calculation_details": FIXTURE["expanded"]}
    source, target = tmp_path / "in.json.gz", tmp_path / "out.json.gz"
    source.write_bytes(gzip.compress(json.dumps(bundle, ensure_ascii=False).encode()))
    compact_bundle(source, target)
    published = json.loads(gzip.decompress(target.read_bytes()))
    assert published["calculation_details"]["format"] == "by_code_v1"
    published["calculation_details"] = expand_calculation_details(published["calculation_details"])
    assert canonical(published) == canonical(bundle)
