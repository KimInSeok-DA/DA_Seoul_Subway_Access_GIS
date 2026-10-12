"""역 원본을 정제해 역 단위 점 데이터로 만든다.

1. 전국도시철도역사정보(기준 출처)를 읽고 이름을 정규화한다(괄호 부기·끝의 '역' 제거)
2. 서울시 역사마스터와 같은 이름끼리 대조해, 500m 넘게 차이 나면 서울시 좌표로 바꾼다(5km 넘으면 다른 도시의 같은 이름이라 보지 않음)
3. 이름이 같고 500m 안에 있는 행(노선별 행)을 한 역으로 합친다. 노선 목록은 보존한다

결과: data/processed/stations.geojson (EPSG:4326), outputs/station_fixes.csv (좌표를 바꾼 행)
"""
import json
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NAT = ROOT / "data" / "raw" / "전체_도시철도역사정보_20260630.xlsx"
SEOUL = ROOT / "data" / "raw" / "seoul_subway_station_master.json"
OUT = ROOT / "data" / "processed" / "stations.geojson"
FIXES = ROOT / "outputs" / "station_fixes.csv"

CRS_M = 5179        # 거리 계산용 투영 좌표계(m)
FIX_MIN_M = 500     # 이 거리보다 차이 나면 좌표 보정
FIX_MAX_M = 5000    # 이 거리보다 멀면 같은 역이 아니라 봄
MERGE_M = 500       # 같은 이름이 이 거리 안이면 한 역


def norm_name(name: str) -> str:
    n = re.sub(r"\(.*?\)", "", str(name)).strip()
    return re.sub(r"역$", "", n) if len(n) > 2 else n


def load_national() -> gpd.GeoDataFrame:
    df = pd.read_excel(NAT, dtype=str)
    # 같은 노선·역번호가 이름만 달리 두 번 있는 행(예: 7호선 0736 '이수'와 '총신대입구(이수)') → 괄호 부기가 있는 쪽을 남김
    df = df.sort_values("역사명", key=lambda s: ~s.str.contains(r"\(")).drop_duplicates(["노선명", "역번호"])
    df["key"] = df["역사명"].map(norm_name)
    # 기준일: '1900-01-00' 같은 잘못된 값은 결측으로
    df["기준일"] = pd.to_datetime(df["데이터기준일자"].str[:10], errors="coerce")
    df.loc[df["기준일"].dt.year < 2000, "기준일"] = pd.NaT
    g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["역경도"].astype(float), df["역위도"].astype(float)), crs=4326)
    return g.to_crs(CRS_M)


def load_seoul() -> gpd.GeoDataFrame:
    sm = pd.DataFrame(json.loads(SEOUL.read_text(encoding="utf-8"))["rows"])
    sm["key"] = sm["BLDN_NM"].map(norm_name)
    g = gpd.GeoDataFrame(sm, geometry=gpd.points_from_xy(sm["LOT"].astype(float), sm["LAT"].astype(float)), crs=4326)
    return g.to_crs(CRS_M)


def fix_coords(nat: gpd.GeoDataFrame, sm: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    nat = nat.copy()
    nat["coord_fixed"] = False
    log = []
    for i, r in nat.iterrows():
        cand = sm[sm.key == r.key]
        if cand.empty:
            continue
        d = cand.geometry.distance(r.geometry)
        j = d.idxmin()
        if FIX_MIN_M < d[j] <= FIX_MAX_M:
            log.append({"역번호": r["역번호"], "역사명": r["역사명"], "노선명": r["노선명"],
                        "원본_위도": r["역위도"], "원본_경도": r["역경도"],
                        "보정_위도": sm.at[j, "LAT"], "보정_경도": sm.at[j, "LOT"],
                        "서울시_역명": sm.at[j, "BLDN_NM"], "서울시_노선": sm.at[j, "ROUTE"], "차이_m": round(d[j])})
            nat.at[i, "geometry"] = sm.at[j, "geometry"]
            nat.at[i, "coord_fixed"] = True
    return nat, pd.DataFrame(log)


def merge_stations(nat: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """같은 이름이고 MERGE_M 안이면 같은 역. 이름별로 가까운 행끼리 묶는다(연결 요소)."""
    nat = nat.copy()
    nat["sid"] = -1
    next_id = 0
    for _, grp in nat.groupby("key"):
        idx = list(grp.index)
        parent = {i: i for i in idx}

        def find(i):
            while parent[i] != i:
                i = parent[i]
            return i

        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                if grp.geometry[idx[a]].distance(grp.geometry[idx[b]]) <= MERGE_M:
                    parent[find(idx[a])] = find(idx[b])
        roots = {}
        for i in idx:
            r = find(i)
            if r not in roots:
                roots[r] = next_id
                next_id += 1
            nat.at[i, "sid"] = roots[r]

    out = []
    for sid, grp in nat.groupby("sid"):
        lines = sorted(set(grp["노선명"].str.replace(r"\s+", " ", regex=True)))
        out.append({
            "station_id": f"S{sid:04d}",
            "name": grp["key"].iloc[0],
            "name_full": max(grp["역사명"], key=len),
            "lines": ";".join(lines),
            "n_lines": len(lines),
            "operators": ";".join(sorted(set(grp["운영기관명"]))),
            "n_rows": len(grp),
            "coord_fixed": bool(grp["coord_fixed"].any()),
            "ref_date": grp["기준일"].max().strftime("%Y-%m-%d") if grp["기준일"].notna().any() else None,
            "addresses": " | ".join(sorted(set(grp["역사도로명주소"].dropna()))),  # 검증용(괄호 안 법정동)
            "geometry": grp.geometry.union_all().centroid,  # 노선별 행의 가운데(m 좌표계)
        })
    return gpd.GeoDataFrame(out, geometry="geometry", crs=CRS_M)


def main() -> None:
    nat = load_national()
    sm = load_seoul()
    nat, fixes = fix_coords(nat, sm)
    st = merge_stations(nat).to_crs(4326)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    FIXES.parent.mkdir(parents=True, exist_ok=True)
    st.to_file(OUT, driver="GeoJSON")
    fixes.to_csv(FIXES, index=False, encoding="utf-8-sig", lineterminator="\n")

    print(f"원본 {pd.read_excel(NAT, usecols=[0]).shape[0]}행 → 중복 행 제거 후 {len(nat)}행 → 역 {len(st)}개 (좌표 보정 {len(fixes)}행)")
    print(f"저장 → {OUT.relative_to(ROOT)}, {FIXES.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
