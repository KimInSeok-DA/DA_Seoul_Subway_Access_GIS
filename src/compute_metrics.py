"""법정동별 지하철 접근성 지표를 계산한다. 거리·면적은 EPSG:5179(m)에서 계산한다.

- near_dist_m: 동 대표점(representative_point, 항상 폴리곤 안)에서 가장 가까운 역까지 직선거리
- n_station: 동 경계 안의 역 수(역 단위, 노선 중복 없음)
- cover_500m: 역 500m 반경이 동 면적을 덮는 비율(%)

역은 서울 경계 + 5km 안의 것만 쓴다(서울 밖 역이 더 가까운 동이 있음).
결과: data/processed/seoul_emd_metrics.geojson, data/processed/stations_study.geojson (EPSG:4326)
"""
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
EMD = ROOT / "data" / "processed" / "seoul_emd.geojson"
STATIONS = ROOT / "data" / "processed" / "stations.geojson"
OUT = ROOT / "data" / "processed" / "seoul_emd_metrics.geojson"
OUT_ST = ROOT / "data" / "processed" / "stations_study.geojson"

CRS_M = 5179
BUFFER_M = 5000   # 서울 경계 밖으로 포함할 역 범위
RADIUS_M = 500    # 역세권 반경


def main() -> None:
    emd = gpd.read_file(EMD).to_crs(CRS_M)
    st = gpd.read_file(STATIONS).to_crs(CRS_M)

    seoul = emd.union_all()
    st = st[st.within(seoul.buffer(BUFFER_M))].copy()
    st["in_seoul"] = st.within(seoul)

    emd["area_km2"] = (emd.area / 1e6).round(3)

    # 1) 대표점 → 최근접 역
    pts = emd[["bjd_cd"]].copy().set_geometry(emd.representative_point(), crs=CRS_M)
    near = gpd.sjoin_nearest(pts, st[["name", "geometry"]], distance_col="near_dist_m", how="left")
    near = near.drop_duplicates("bjd_cd")  # 거리가 같은 역이 둘이면 하나만
    emd = emd.merge(near[["bjd_cd", "name", "near_dist_m"]].rename(columns={"name": "near_station"}), on="bjd_cd")
    emd["near_dist_m"] = emd["near_dist_m"].round(0).astype(int)

    # 2) 동 안의 역 수
    inside = gpd.sjoin(st[["station_id", "geometry"]], emd[["bjd_cd", "geometry"]], predicate="within")
    emd["n_station"] = emd["bjd_cd"].map(inside.groupby("bjd_cd").size()).fillna(0).astype(int)

    # 3) 500m 반경이 덮는 면적 비율
    cover = st.buffer(RADIUS_M).union_all()
    emd["cover_500m"] = (emd.intersection(cover).area / emd.area * 100).round(1)

    cols = ["bjd_cd", "sgg_cd", "sgg_nm", "emd_nm", "full_nm", "area_km2",
            "near_station", "near_dist_m", "n_station", "cover_500m", "collected", "geometry"]
    emd[cols].to_crs(4326).to_file(OUT, driver="GeoJSON")
    st.to_crs(4326).to_file(OUT_ST, driver="GeoJSON")

    print(f"법정동 {len(emd)}개, 역 {len(st)}개(서울 안 {st['in_seoul'].sum()}, 서울 밖 5km 안 {(~st['in_seoul']).sum()})")
    print(f"near_dist_m 최대 {emd['near_dist_m'].max()}m (완충 {BUFFER_M}m보다 작아야 서울 밖 역 누락이 없음)")
    print(f"저장 → {OUT.relative_to(ROOT)}, {OUT_ST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
