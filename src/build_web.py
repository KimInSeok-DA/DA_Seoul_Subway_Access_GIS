"""GitHub Pages 공개 지도용 데이터를 만든다(docs/map/data.js).

- 경계를 EPSG:5179에서 1m 허용오차로 단순화하고 좌표를 소수 5자리(약 1m)로 줄여 파일을 가볍게 한다
  (5m는 아주 작은 도심 동의 면적이 최대 3.9% 달라져 1m로 줄임. 동별 면적 차이가 1%를 넘으면 멈춘다)
- 속성은 지도에 쓰는 것만 남긴다. 단순화 전후 건수와 지표 값은 바뀌지 않는다(지표는 원본 경계로 이미 계산됨)
- file://로 열어도 동작하도록 GeoJSON을 JS 변수로 넣는다
"""
import json
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
OUT = ROOT / "docs" / "map" / "data.js"
SIMPLIFY_M = 1
MAX_AREA_DIFF_PCT = 1.0   # 지도에 그린 경계와 원본의 동별 면적 차이 허용치

EMD_COLS = ["bjd_cd", "sgg_nm", "emd_nm", "area_km2", "near_station", "near_dist_m", "n_station", "cover_500m"]
ST_COLS = ["name", "name_full", "lines", "operators", "in_seoul", "coord_fixed", "ref_date"]


def round_coords(obj, nd=5):
    if isinstance(obj, list):
        return [round_coords(o, nd) for o in obj]
    return round(obj, nd) if isinstance(obj, float) else obj


def to_fc(g: gpd.GeoDataFrame, cols: list[str]) -> dict:
    fc = json.loads(g[cols + ["geometry"]].to_json(drop_id=True))
    for f in fc["features"]:
        f["geometry"]["coordinates"] = round_coords(f["geometry"]["coordinates"])
    return fc


def main() -> None:
    emd = gpd.read_file(P / "seoul_emd_metrics.geojson")
    st = gpd.read_file(P / "stations_study.geojson")
    st["ref_date"] = st["ref_date"].astype(str).str[:10].replace({"NaT": None, "None": None})
    st["in_seoul"] = st["in_seoul"].astype(bool)
    st["coord_fixed"] = st["coord_fixed"].astype(bool)

    simp = emd.to_crs(5179)
    simp["geometry"] = simp.geometry.simplify(SIMPLIFY_M, preserve_topology=True)
    simp = simp.to_crs(4326)
    if not simp.is_valid.all() or simp.is_empty.any() or len(simp) != len(emd):
        raise RuntimeError("단순화 후 도형 이상")

    # 실제로 내보낼 도형(단순화 + 좌표 반올림)의 면적을 원본과 비교
    fc_emd = to_fc(simp, EMD_COLS)
    drawn = gpd.GeoDataFrame.from_features(fc_emd["features"], crs=4326).to_crs(5179)
    orig = emd.to_crs(5179)
    diff = ((drawn.area.values - orig.area.values) / orig.area.values * 100)
    worst = abs(diff).max()
    if worst > MAX_AREA_DIFF_PCT:
        raise RuntimeError(f"지도용 경계 면적 차이 최대 {worst:.2f}% > {MAX_AREA_DIFF_PCT}%")

    meta = {"n_emd": len(emd), "n_station": len(st), "collected": str(emd["collected"].iloc[0])[:10]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "// src/build_web.py가 만든 파일. 직접 고치지 않는다\n"
        f"const META = {json.dumps(meta, ensure_ascii=False)};\n"
        f"const EMD = {json.dumps(to_fc(simp, EMD_COLS), ensure_ascii=False, separators=(',', ':'))};\n"
        f"const STATIONS = {json.dumps(to_fc(st, ST_COLS), ensure_ascii=False, separators=(',', ':'))};\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"법정동 {len(simp)}개(면적 차이 최대 {worst:.2f}%), 역 {len(st)}개 → {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.2f}MB)")


if __name__ == "__main__":
    main()
