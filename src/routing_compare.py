"""ArcGIS 경로 서비스(Location Platform)로 동 대표점 → 역 도보 거리를 구해 직선거리와 비교한다.

- 동마다 직선거리로 가까운 역 3개 → 각각 도보 경로 → 가장 짧은 도보 거리를 그 동의 값으로
- 이동 방식은 이름이 아니라 종류로 고른다(계정 언어에 따라 이름이 '도보 거리'처럼 바뀜): type=WALK, 기준 Kilometers
- 경로 거리는 도로망 위 거리라, 도보 거리 = 대표점→길 + 길 위 경로 + 길→역 (정류장의 DistanceToNetworkInMeters)
- 동별 결과는 data/raw/(git 제외)에만 저장하고, 공개용으로는 요약 통계만 outputs/routing_summary.md에 쓴다
  (경로 결과의 저장·공개 조건을 Esri 문서에서 확인하지 못함 → 1012_04)
- 무료 사용량(단순 경로 월 20,000건) 안에서만: 실행 전 요청 건수를 출력하고 MAX_ROUTES를 넘으면 멈춘다

    python src/routing_compare.py             # 경로 서비스 호출(약 1,400건) → 요약
    python src/routing_compare.py --from-raw  # 저장한 응답(data/raw/routing/)으로 요약만 다시(호출 없음)
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw" / "routing"
REPORT = ROOT / "outputs" / "routing_summary.md"

K = 3              # 동마다 직선거리로 가까운 역 몇 개까지 도보 경로를 구할지
BATCH = 50         # 한 요청에 넣는 경로 수(정류장 100개)
MAX_ROUTES = 2000  # 한 번 실행에 쓰는 최대 경로 수(무료 20,000건/월 안쪽)


def pairs() -> pd.DataFrame:
    emd = gpd.read_file(P / "seoul_emd_metrics.geojson").to_crs(5179)
    st = gpd.read_file(P / "stations_study.geojson").to_crs(5179)
    rep = emd.representative_point()
    sx, sy = st.geometry.x.values, st.geometry.y.values
    rows = []
    for i, p in enumerate(rep):
        d = np.hypot(sx - p.x, sy - p.y)
        for rank, j in enumerate(np.argsort(d)[:K]):
            rows.append({"bjd_cd": emd.bjd_cd.iloc[i], "sgg_nm": emd.sgg_nm.iloc[i], "rank": rank,
                         "station": st.name.iloc[j], "straight_m": d[j], "px": p.x, "py": p.y, "sx": sx[j], "sy": sy[j]})
    df = pd.DataFrame(rows)
    # 경로 서비스에는 경위도로 보냄
    o = gpd.GeoSeries(gpd.points_from_xy(df.px, df.py), crs=5179).to_crs(4326)
    s = gpd.GeoSeries(gpd.points_from_xy(df.sx, df.sy), crs=5179).to_crs(4326)
    df["olon"], df["olat"], df["slon"], df["slat"] = o.x, o.y, s.x, s.y
    df["route_id"] = [f"R{i:05d}" for i in range(len(df))]
    return df


def solve(url: str, token: str, mode: dict, batch: pd.DataFrame) -> tuple[list, list]:
    feats = []
    for r in batch.itertuples():
        feats.append({"geometry": {"x": r.olon, "y": r.olat}, "attributes": {"Name": r.route_id + "_o", "RouteName": r.route_id}})
        feats.append({"geometry": {"x": r.slon, "y": r.slat}, "attributes": {"Name": r.route_id + "_s", "RouteName": r.route_id}})
    data = {"f": "json", "token": token, "travelMode": json.dumps(mode),
            "stops": json.dumps({"features": feats, "spatialReference": {"wkid": 4326}}),
            "returnRoutes": "true", "returnStops": "true", "returnDirections": "false",
            "outputLines": "esriNAOutputLineNone"}
    for wait in (3, 10, 30, None):
        try:
            res = requests.post(url + "/solve", data=data, timeout=180).json()
            if "error" not in res:
                return res["routes"]["features"], res["stops"]["features"]
            err = res["error"]
        except (requests.RequestException, ValueError, KeyError) as e:
            err = repr(e)
        if wait is None:
            raise RuntimeError(f"경로 요청 실패: {err}")
        time.sleep(wait)


def fetch(df: pd.DataFrame) -> dict:
    from arcgis.gis import GIS

    load_dotenv(ROOT / ".env")
    print(f"동 {df.bjd_cd.nunique()}개 × 역 {K}개 = 경로 {len(df)}건 요청 예정(요청 {int(np.ceil(len(df) / BATCH))}회)")
    if len(df) > MAX_ROUTES:
        sys.exit(f"경로 {len(df)}건 > 한도 {MAX_ROUTES}건 → 멈춤")

    gis = GIS(os.environ["ARCGIS_URL"], os.environ["ARCGIS_USERNAME"], os.environ["ARCGIS_PASSWORD"])
    url = gis.properties["helperServices"]["route"]["url"]
    token = gis._con.token
    modes = requests.get(url + "/retrieveTravelModes", params={"f": "json", "token": token}, timeout=60).json()["supportedTravelModes"]
    mode = next(m for m in modes if m.get("type") == "WALK" and "Kilometers" in m.get("impedanceAttributeName", ""))
    print(f"이동 방식: {mode['name']} (type={mode['type']}, 기준={mode['impedanceAttributeName']})")

    routes, stops = [], []
    for i in range(0, len(df), BATCH):
        r, s = solve(url, token, mode, df.iloc[i:i + BATCH])
        routes += r
        stops += s
        print(f"  {min(i + BATCH, len(df))}/{len(df)}", end="\r")
    print()

    raw = {"run": datetime.now().isoformat(timespec="seconds"), "mode": mode["name"], "routes": routes, "stops": stops}
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "walk_routes_raw.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return raw


def main() -> int:
    df = pairs()
    if "--from-raw" in sys.argv:
        raw = json.loads((RAW / "walk_routes_raw.json").read_text(encoding="utf-8"))
        print(f"저장한 응답으로 다시 계산(실행 {raw['run']}, 경로 {len(raw['routes'])}건, 서비스 호출 없음)")
    else:
        raw = fetch(df)
    mode, routes, stops = {"name": raw["mode"]}, raw["routes"], raw["stops"]

    walk = {f["attributes"]["Name"]: f["attributes"]["Total_Kilometers"] * 1000 for f in routes}
    snap = {f["attributes"]["Name"]: f["attributes"].get("DistanceToNetworkInMeters") for f in stops}
    df["network_m"] = df.route_id.map(walk)
    df["origin_snap_m"] = df.route_id.map(lambda x: snap.get(x + "_o"))
    df["station_snap_m"] = df.route_id.map(lambda x: snap.get(x + "_s"))
    df["walk_m"] = df.network_m + df.origin_snap_m + df.station_snap_m
    n_fail = df.walk_m.isna().sum()
    df.to_csv(RAW / "walk_routes_pairs.csv", index=False, encoding="utf-8-sig")

    # 동별: 도보로 가장 가까운 역
    # 동마다 도보 거리가 가장 짧은 '행'을 고른다(groupby().first()는 열마다 따로 값을 골라 행이 섞일 수 있음)
    ok = df.dropna(subset=["walk_m"])
    best = ok.loc[ok.groupby("bjd_cd").walk_m.idxmin()].set_index("bjd_cd")
    near = df[df["rank"] == 0].set_index("bjd_cd")
    best["straight_nearest_m"] = near.straight_m
    best["ratio"] = best.walk_m / best.straight_m                     # 같은 역까지 도보 / 직선
    best["ratio_vs_nearest"] = best.walk_m / best.straight_nearest_m  # 도보 최소 / 직선 최소
    best["changed"] = best.station != near.station
    best.to_csv(RAW / "walk_by_emd.csv", encoding="utf-8-sig")

    labels = ["0～300", "300～500", "500～800", "800～1,200", "1,200 초과"]

    def cls(v):
        return pd.cut(v, [-1, 300, 500, 800, 1200, 1e9], labels=labels)
    # 동이 없는 구간도 행·열로 남겨 5×5를 고정(빠지면 '한 단계 이상 멀어짐'을 셀 때 위치가 밀림)
    shift = pd.crosstab(cls(best.straight_nearest_m), cls(best.walk_m)).reindex(index=labels, columns=labels, fill_value=0)
    up = int(sum(shift.iloc[i, j] for i in range(5) for j in range(5) if j > i))
    q = best.ratio.quantile([.1, .5, .9])
    gu = best.groupby("sgg_nm").ratio_vs_nearest.median().sort_values()

    lines = [
        "# 도보 거리와 직선거리 비교 (ArcGIS 경로 서비스)", "",
        f"- 응답 저장: {raw['run'][:16].replace('T', ' ')}, 이동 방식 `{mode['name']}`(type WALK, 기준 거리), 경로 {len(df)}건(실패 {n_fail})",
        f"- 방법: 법정동 {len(best)}개의 대표점에서 직선거리로 가까운 역 {K}개까지 도보 경로를 구하고, 가장 짧은 도보 거리를 그 동의 값으로 씀",
        "- 동별 값은 공개하지 않고 요약만 싣는다(경로 결과의 저장·공개 조건 미확인)", "",
        "## 요약", "",
        "| 항목 | 값 |", "|---|---|",
        f"| 같은 역까지 도보 ÷ 직선 (우회 비율) | 중앙값 {q[.5]:.2f}배 (10%: {q[.1]:.2f}, 90%: {q[.9]:.2f}) |",
        f"| 가장 가까운 역까지 거리 중앙값 | 직선 {best.straight_nearest_m.median():,.0f}m → 도보 {best.walk_m.median():,.0f}m |",
        f"| 도보로 가장 가까운 역이 직선 기준과 다른 동 | {int(best.changed.sum())}개 / {len(best)} |",
        f"| 도보로 보면 거리 구간이 한 단계 이상 멀어지는 동 | {up}개 / {len(best)} |",
        f"| 우회 비율 3배 넘는 동 | {int((best.ratio > 3).sum())}개(한강변에 대표점이 찍혀 강변도로 쪽에 붙은 동 포함 → 실제 도보 거리가 아님) |",
        f"| 3배 넘는 동을 뺀 우회 비율 | 중앙값 {best.ratio[best.ratio <= 3].median():.2f}배 |",
        f"| 대표점에서 도로망까지 거리 | 중앙값 {best.origin_snap_m.median():.0f}m, 100m 넘는 동 {int((best.origin_snap_m > 100).sum())}개(산지 등, 도보 거리에 포함) |", "",
        "## 구간 이동 (행: 직선 기준, 열: 도보 기준, 동 수)", "",
        "| 직선 \\ 도보 | " + " | ".join(shift.columns.astype(str)) + " |",
        "|---|" + "---|" * len(shift.columns),
    ] + [f"| {idx} | " + " | ".join(str(v) for v in row) + " |" for idx, row in shift.iterrows()] + [
        "", "## 구별 우회 비율 (도보 최소 ÷ 직선 최소, 동 중앙값)", "",
        f"- 가장 작은 3개 구: " + ", ".join(f"{k} {v:.2f}배" for k, v in gu.head(3).items()),
        f"- 가장 큰 3개 구: " + ", ".join(f"{k} {v:.2f}배" for k, v in gu.tail(3).items()),
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines[6:16]))
    print(f"→ {REPORT.relative_to(ROOT)} (동별 값은 {RAW.relative_to(ROOT)}에만)")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
