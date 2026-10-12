"""PostGIS로 같은 지표를 SQL로 다시 계산해 Python 결과와 대조한다(outputs/postgis_crosscheck.md).

먼저 `docker compose up -d`로 PostGIS를 띄운다. Docker가 필요해서 run.py에는 넣지 않은 별도 검증이다.

- 입력: 원본 경계(data/processed/seoul_emd.geojson)와 정제된 전체 역(stations.geojson). Python 지표 결과는 넣지 않는다
- 계산: sql/metrics.sql (서울+5km 역 필터, 대표점 KNN 최근접, ST_Within, ST_Intersection 면적)
- 허용 오차: 거리 1m(반올림), 비율 0.1%p(반올림), 역 수·최근접 역 이름은 같아야 함
"""
import os
import sys
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
SQL = ROOT / "sql" / "metrics.sql"
REPORT = ROOT / "outputs" / "postgis_crosscheck.md"


def main() -> int:
    load_dotenv(ROOT / ".env")
    eng = create_engine(f"postgresql+psycopg://gis:{os.environ['POSTGIS_PASSWORD']}@127.0.0.1:5433/subway_access")

    emd = gpd.read_file(P / "seoul_emd.geojson")[["bjd_cd", "emd_nm", "geometry"]].rename_geometry("geom")
    st = gpd.read_file(P / "stations.geojson")[["station_id", "name", "geometry"]].rename_geometry("geom")
    emd.to_postgis("emd", eng, if_exists="replace", index=False)
    st.to_postgis("stations", eng, if_exists="replace", index=False)

    with eng.begin() as con:
        version = con.execute(text("SELECT postgis_lib_version()")).scalar()
        t0 = datetime.now()
        con.execute(text(SQL.read_text(encoding="utf-8")))
        secs = (datetime.now() - t0).total_seconds()
        n_st = con.execute(text("SELECT COUNT(*) FROM st_m")).scalar()
    sql = pd.read_sql("SELECT * FROM metrics_sql", eng)

    py = gpd.read_file(P / "seoul_emd_metrics.geojson").drop(columns="geometry")
    m = py.merge(sql, on="bjd_cd", suffixes=("_py", "_sql"), how="outer", indicator=True)

    d_dist = (m["near_dist_m_py"] - m["near_dist_m_sql"]).abs()
    d_cover = (m["cover_500m_py"] - m["cover_500m_sql"].astype(float)).abs()
    name_diff = m[m["near_station_py"] != m["near_station_sql"]]
    checks = [
        ("법정동 행 수(Python / SQL)", len(py) == len(sql) == (m["_merge"] == "both").sum(), f"{len(py)} / {len(sql)}"),
        ("서울+5km 역 수(Python 389와 같음)", n_st == 389, f"{n_st}"),
        ("가장 가까운 역 이름 일치", name_diff.empty, f"불일치 {len(name_diff)}"),
        ("가장 가까운 역까지 거리 차이 1m 이하", (d_dist <= 1).all(), f"최대 {d_dist.max():.0f}m, 0m인 동 {(d_dist == 0).sum()}"),
        ("동 안의 역 수 일치", (m["n_station_py"] == m["n_station_sql"]).all(),
         f"불일치 {(m['n_station_py'] != m['n_station_sql']).sum()}"),
        ("역 500m 안 면적 비율 차이 0.1%p 이하", (d_cover <= 0.1 + 1e-9).all(),
         f"최대 {d_cover.max():.1f}%p, 같은 동 {(d_cover < 1e-9).sum()}"),
    ]
    n_fail = sum(not ok for _, ok, _ in checks)

    lines = [
        "# PostGIS 교차 검증", "",
        f"- 실행: {datetime.now():%Y-%m-%d %H:%M}, PostGIS {version}, SQL 실행 {secs:.1f}초",
        "- 같은 원본(경계·정제된 역)을 PostGIS에 넣고 `sql/metrics.sql`로 지표를 다시 계산해 Python 결과와 대조",
        f"- 결과: **{'일치' if n_fail == 0 else f'불일치 {n_fail}건'}**", "",
        "| 검사 | 결과 | 내용 |", "|---|---|---|",
    ] + [f"| {n} | {'통과' if ok else '**실패**'} | {d} |" for n, ok, d in checks]
    if not name_diff.empty:
        lines += ["", "최근접 역 이름이 다른 동:", ""] + [
            f"- {r.emd_nm_py}: Python {r.near_station_py} {r.near_dist_m_py}m / SQL {r.near_station_sql} {r.near_dist_m_sql}m"
            for r in name_diff.itertuples()]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    for n, ok, d in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {n} — {d}")
    print(f"→ {REPORT.relative_to(ROOT)}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
