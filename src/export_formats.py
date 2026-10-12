"""검증을 통과한 결과를 여러 공간데이터 포맷으로 내보낸다(docs/downloads/, 공개 지도에서 내려받기).

- GeoPackage: 레이어 2개(emd, stations)를 파일 하나에. 필드 이름·타입이 그대로 유지됨
- Shapefile(zip): 필드 이름 10자 제한 → 짧은 이름으로 바꾸고 대응표를 남김. 인코딩 UTF-8(.cpg)
- CSV: 도형 없이 속성 + 점 좌표(법정동은 대표점, 역은 역 위치). Excel에서 한글이 깨지지 않게 UTF-8 BOM
- GeoJSON은 data/processed/에 이미 있어 복사하지 않고 공개 지도에서 저장소 원본으로 링크한다

모든 파일을 다시 읽어 건수·값이 원본과 같은지 확인하고, 다르면 멈춘다.
파일 안에 들어가는 날짜(GPKG 변경 시각, .dbf 헤더 날짜, zip 항목 시각)는 실행 시각 대신 경계 수집일로 고정한다.
→ 데이터가 같으면 파일도 바이트까지 같아서, 다시 실행해도 git에 변경으로 잡히지 않는다.
"""
import os
import shutil
import tempfile
import zipfile
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
OUT = ROOT / "docs" / "downloads"
BASE = "seoul_subway_access"

EMD_COLS = ["bjd_cd", "sgg_cd", "sgg_nm", "emd_nm", "full_nm", "area_km2",
            "near_station", "near_dist_m", "n_station", "cover_500m", "collected"]
ST_COLS = ["station_id", "name", "name_full", "lines", "n_lines", "operators", "in_seoul", "coord_fixed", "ref_date"]
# Shapefile은 필드 이름이 10자까지
SHP_NAMES = {"near_station": "near_stn", "near_dist_m": "near_dist", "coord_fixed": "coord_fix"}


def load() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    emd = gpd.read_file(P / "seoul_emd_metrics.geojson")[EMD_COLS + ["geometry"]]
    st = gpd.read_file(P / "stations_study.geojson")[ST_COLS + ["geometry"]]
    # 날짜는 문자열(YYYY-MM-DD)로 통일해 포맷마다 타입이 달라지지 않게 함
    emd["collected"] = emd["collected"].astype(str).str[:10]
    st["ref_date"] = st["ref_date"].astype(str).str[:10].replace({"NaT": None, "None": None})
    st["in_seoul"] = st["in_seoul"].astype(int)
    st["coord_fixed"] = st["coord_fixed"].astype(int)
    return emd, st


def fix_dbf_date(dbf: Path, d: date) -> None:
    """.dbf 헤더 1～3바이트(마지막 수정일: 1900년부터 연, 월, 일)를 고정 날짜로"""
    b = bytearray(dbf.read_bytes())
    b[1:4] = bytes([d.year - 1900, d.month, d.day])
    dbf.write_bytes(bytes(b))


def fixed_zip(src_dir: Path, out_zip: Path, d: date) -> None:
    """파일 순서·시각·권한을 고정한 zip"""
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(src_dir.iterdir()):
            info = zipfile.ZipInfo(f.name, date_time=(d.year, d.month, d.day, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, f.read_bytes())


def same(a: pd.DataFrame, b: pd.DataFrame, cols: list[str], name: str) -> None:
    if len(a) != len(b):
        raise RuntimeError(f"{name}: 건수 {len(b)} != {len(a)}")
    x = a[cols].reset_index(drop=True).astype(str)
    y = b[cols].reset_index(drop=True).astype(str)
    bad = [c for c in cols if not x[c].equals(y[c])]
    if bad:
        raise RuntimeError(f"{name}: 값이 다른 필드 {bad}")


def main() -> None:
    emd, st = load()
    stamp = date.fromisoformat(emd["collected"].iloc[0])
    os.environ["OGR_CURRENT_DATE"] = f"{stamp.isoformat()}T00:00:00.000Z"  # GDAL이 GPKG에 쓰는 변경 시각
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # GeoPackage
    gpkg = OUT / f"{BASE}.gpkg"
    emd.to_file(gpkg, layer="emd", driver="GPKG")
    st.to_file(gpkg, layer="stations", driver="GPKG")
    same(emd, gpd.read_file(gpkg, layer="emd"), EMD_COLS, "GPKG emd")
    same(st, gpd.read_file(gpkg, layer="stations"), ST_COLS, "GPKG stations")

    # Shapefile(zip)
    tmp = Path(tempfile.mkdtemp())
    for layer, g, cols in (("emd", emd, EMD_COLS), ("stations", st, ST_COLS)):
        d = tmp / f"{BASE}_{layer}"
        d.mkdir()
        g.rename(columns=SHP_NAMES).to_file(d / f"{BASE}_{layer}.shp", encoding="UTF-8")
        back = gpd.read_file(d / f"{BASE}_{layer}.shp").rename(columns={v: k for k, v in SHP_NAMES.items()})
        same(g, back, cols, f"SHP {layer}")
        fix_dbf_date(d / f"{BASE}_{layer}.dbf", stamp)
        fixed_zip(d, OUT / f"{BASE}_{layer}_shp.zip", stamp)

    # CSV(속성 + 점 좌표)
    rep = emd.to_crs(5179).representative_point().to_crs(4326)
    emd_csv = emd.drop(columns="geometry").assign(rep_lon=rep.x.round(6), rep_lat=rep.y.round(6))
    st_csv = st.drop(columns="geometry").assign(lon=st.geometry.x.round(6), lat=st.geometry.y.round(6))
    emd_csv.to_csv(OUT / f"{BASE}_emd.csv", index=False, encoding="utf-8-sig")
    st_csv.to_csv(OUT / f"{BASE}_stations.csv", index=False, encoding="utf-8-sig")
    same(emd_csv, pd.read_csv(OUT / f"{BASE}_emd.csv", dtype={"bjd_cd": str, "sgg_cd": str}), EMD_COLS, "CSV emd")
    same(st_csv, pd.read_csv(OUT / f"{BASE}_stations.csv").fillna({"ref_date": "None"}).replace({"ref_date": {"None": None}}),
         [c for c in ST_COLS if c != "ref_date"], "CSV stations")

    for f in sorted(OUT.iterdir()):
        print(f"  {f.name:<42} {f.stat().st_size / 1e6:6.2f}MB")
    print(f"내보내기 완료(다시 읽어 건수·값 대조 통과): 법정동 {len(emd)}, 역 {len(st)} → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
