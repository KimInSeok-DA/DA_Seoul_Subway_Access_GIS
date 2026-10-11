"""VWorld 행정구역도 WFS(OGC)로 서울 법정동(읍면동) 경계를 받는다.

- 레이어 `lt_c_ademd_info`, OGC Filter로 법정동코드(emd_cd)가 11로 시작하는 것만
- 원본 응답은 data/raw/에 저장하고, 정리한 경계는 data/processed/에 저장
- 확인: 응답 numberMatched = 받은 건수, 코드 중복 0, 법정동코드 표(국토교통부)의 서울 법정동과 코드 단위로 일치

결과: data/processed/seoul_emd.geojson (EPSG:4326)
"""
import json
import os
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "vworld_lt_c_ademd_info_seoul.json"
CODES = ROOT / "data" / "reference" / "법정동코드_국토교통부_20260630.csv"
OUT = ROOT / "data" / "processed" / "seoul_emd.geojson"
URL = "https://api.vworld.kr/req/wfs"
DOMAIN = "https://github.com/KimInSeok-DA/DA_Seoul_Subway_Access_GIS"  # VWorld 키 요청 시 함께 보내는 서비스 주소

SEOUL_FILTER = (
    '<ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">'
    '<ogc:PropertyIsLike wildCard="*" singleChar="." escapeChar="!">'
    "<ogc:PropertyName>emd_cd</ogc:PropertyName><ogc:Literal>11*</ogc:Literal>"
    "</ogc:PropertyIsLike></ogc:Filter>"
)


def fetch(key: str) -> dict:
    params = {"key": key, "domain": DOMAIN, "SERVICE": "WFS", "VERSION": "1.1.0", "REQUEST": "GetFeature",
              "TYPENAME": "lt_c_ademd_info", "SRSNAME": "EPSG:4326", "OUTPUT": "application/json",
              "MAXFEATURES": 1000, "FILTER": SEOUL_FILTER}
    r = requests.get(URL, params=params, timeout=180)
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        raise RuntimeError(f"WFS 응답이 JSON이 아님: {r.text[:200]}") from None


def seoul_codes() -> pd.DataFrame:
    """법정동코드 표에서 서울의 읍면동 단위(리 없음) 행"""
    d = pd.read_csv(CODES, dtype=str, encoding="utf-8-sig")
    return d[d["법정동코드"].str.startswith("11") & d["읍면동명"].notna() & d["리명"].isna()]


def main() -> None:
    load_dotenv(ROOT / ".env")
    body = fetch(os.environ["VWORLD_API_KEY"])
    n = len(body["features"])
    if body.get("numberMatched") not in (None, n):
        raise RuntimeError(f"받은 건수 {n} != 응답 총건수 {body['numberMatched']}")

    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    g = gpd.GeoDataFrame.from_features(body["features"], crs=4326)
    g["bjd_cd"] = g["emd_cd"] + "00"  # WFS는 8자리, 법정동코드 표는 10자리
    if g["bjd_cd"].duplicated().any():
        raise RuntimeError("법정동코드 중복")

    codes = seoul_codes()
    only_wfs = set(g["bjd_cd"]) - set(codes["법정동코드"])
    only_tbl = set(codes["법정동코드"]) - set(g["bjd_cd"])
    if only_wfs or only_tbl:
        raise RuntimeError(f"코드 불일치: 경계에만 {sorted(only_wfs)}, 코드표에만 {sorted(only_tbl)}")

    g = g.merge(codes[["법정동코드", "시군구명"]], left_on="bjd_cd", right_on="법정동코드", how="left")
    g = g.rename(columns={"emd_kor_nm": "emd_nm", "시군구명": "sgg_nm"})
    g["sgg_cd"] = g["bjd_cd"].str[:5]
    g["collected"] = date.today().isoformat()
    g = g[["bjd_cd", "sgg_cd", "sgg_nm", "emd_nm", "full_nm", "collected", "geometry"]].sort_values("bjd_cd")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    g.to_file(OUT, driver="GeoJSON")
    print(f"서울 법정동 경계 {len(g)}개 (구 {g['sgg_cd'].nunique()}개), 코드표 {len(codes)}개와 일치")
    print(f"저장 → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
