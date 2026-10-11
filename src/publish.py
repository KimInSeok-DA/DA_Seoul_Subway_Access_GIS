"""검증을 통과한 결과를 ArcGIS Online(Location Platform)에 Hosted Feature Layer로 올린다.

- 처음: File Geodatabase(zip) 항목 업로드 → Feature Layer로 게시
  (GeoJSON으로 올리면 ArcGIS가 법정동코드 같은 숫자 모양 문자열을 정수로 추정함 → 열 타입을 저장하는 FGDB 사용)
- 이후: 같은 Feature Layer를 덮어쓰기(항목 ID·URL 유지, Web Map이 깨지지 않음)
- 항목 정보(요약·설명·태그·출처·이용 조건)를 코드로 채운다
- 공유 범위는 바꾸지 않는다(공개 전환은 사람이 한다)

항목 ID는 outputs/arcgis_items.json에 남겨 다음 실행에서 같은 항목을 찾는다.
"""
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

import geopandas as gpd
from dotenv import load_dotenv

import validate

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
STATE = ROOT / "outputs" / "arcgis_items.json"
REPO = "https://github.com/KimInSeok-DA/DA_Seoul_Subway_Access_GIS"

CREDITS = ("국토교통부 행정구역도(VWorld WFS, 공공누리 제1유형), 국가철도공단 전국도시철도역사정보표준데이터, "
           "서울특별시 서울시 역사마스터 정보(공공누리 제1유형), 국토교통부 전국 법정동")
LICENSE = ("원자료의 이용 조건을 따릅니다. 공공누리 제1유형(출처표시) 자료를 포함하므로 이용 시 출처를 표시해 주세요. "
           f"가공 방법과 검증 결과: <a href='{REPO}'>{REPO}</a>")
TAGS = ["서울", "법정동", "지하철", "역세권", "접근성", "공공데이터", "Seoul", "subway", "accessibility"]

LAYERS = {
    "emd": {
        "src": P / "seoul_emd_metrics.geojson",
        "file": "seoul_emd_subway_access",   # 덮어쓰기는 처음 올린 파일 이름과 같아야 함
        "title": "서울 법정동별 지하철 접근성",
        "snippet": "서울 법정동 467개의 최근접 역 거리, 동 안 역 수, 역 500m 반경이 덮는 면적 비율",
        "cols": ["bjd_cd", "sgg_nm", "emd_nm", "area_km2", "near_station", "near_dist_m", "n_station", "cover_500m", "collected"],
    },
    "stations": {
        "src": P / "stations_study.geojson",
        "file": "seoul_subway_stations",
        "title": "서울 및 주변 5km 지하철역",
        "snippet": "접근성 계산에 쓴 지하철역(역 단위, 노선 중복 없음). 서울 안 307개, 서울 경계 밖 5km 안 82개",
        "cols": ["station_id", "name", "name_full", "lines", "n_lines", "operators", "in_seoul", "coord_fixed", "ref_date"],
    },
}


def description(key: str, n: int) -> str:
    common = (f"<p>데이터 기준: 역 표준데이터 파일 2026-06-30(행별 2022～2026), 경계 수집 {date.today().isoformat()}.</p>"
              f"<p>자동 검증(건수·코드·도형·좌표 범위·역 주소 대조 등 21개)을 통과한 결과만 갱신합니다. "
              f"코드와 검증 리포트: <a href='{REPO}'>{REPO}</a></p>")
    if key == "emd":
        return ("<p>서울 법정동별 지하철 접근성 지표입니다. 거리·면적은 EPSG:5179(m)에서 계산했습니다.</p><ul>"
                "<li><b>near_dist_m</b>: 동 대표점(폴리곤 안의 점)에서 가장 가까운 역까지 직선거리(m)</li>"
                "<li><b>n_station</b>: 동 경계 안의 역 수(환승역은 1개)</li>"
                "<li><b>cover_500m</b>: 역 500m 반경이 동 면적을 덮는 비율(%)</li></ul>"
                f"<p>법정동 {n}개. 서울 경계 근처 동을 위해 서울 밖 5km 안의 역도 계산에 포함했습니다.</p>" + common)
    return ("<p>법정동 접근성 계산에 쓴 지하철역입니다. 노선별 행을 역 단위로 합쳤고(lines에 노선 목록), "
            "원본 좌표 오류는 서울시 역사마스터와 대조해 보정했습니다(coord_fixed).</p>"
            f"<p>역 {n}개.</p>" + common)


def to_fgdb_zip(g: gpd.GeoDataFrame, d: Path, name: str) -> Path:
    gdb = d / f"{name}.gdb"
    g.to_file(gdb, driver="OpenFileGDB", layer=name)
    return Path(shutil.make_archive(str(d / name), "zip", root_dir=d, base_dir=gdb.name))


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def wait_count(layer, expected: int, tries: int = 10) -> int:
    """덮어쓰기 직후에는 옛 건수가 나올 수 있어 몇 번 다시 센다"""
    n = -1
    for _ in range(tries):
        n = layer.query(return_count_only=True)
        if n == expected:
            break
        time.sleep(3)
    return n


def main() -> None:
    if validate.main() != 0:
        sys.exit("검증 실패 → 업로드하지 않음")

    from arcgis.features import FeatureLayerCollection
    from arcgis.gis import GIS, ItemProperties, ItemTypeEnum

    load_dotenv(ROOT / ".env")
    gis = GIS(os.environ["ARCGIS_URL"], os.environ["ARCGIS_USERNAME"], os.environ["ARCGIS_PASSWORD"])
    state = load_state()
    tmp = Path(tempfile.mkdtemp())

    for key, cfg in LAYERS.items():
        g = gpd.read_file(cfg["src"])[cfg["cols"] + ["geometry"]]
        f = to_fgdb_zip(g, tmp, cfg["file"])

        item = gis.content.get(state[key]["layer_id"]) if key in state else None
        if item is None:
            props = ItemProperties(title=cfg["title"], item_type=ItemTypeEnum.FILE_GEODATABASE, tags=TAGS, snippet=cfg["snippet"])
            src_item = gis.content.folders.get().add(props, file=str(f)).result()
            item = src_item.publish()
            state[key] = {"layer_id": item.id, "source_id": src_item.id}
            action = "게시"
        else:
            res = FeatureLayerCollection.fromitem(item).manager.overwrite(str(f))
            if not (isinstance(res, dict) and res.get("success")):
                sys.exit(f"{cfg['title']} 덮어쓰기 실패: {res}")
            action = "덮어쓰기"

        item.update(item_properties={"title": cfg["title"], "snippet": cfg["snippet"], "tags": TAGS,
                                     "description": description(key, len(g)),
                                     "accessInformation": CREDITS, "licenseInfo": LICENSE})
        n = wait_count(item.layers[0], len(g))
        if n != len(g):
            sys.exit(f"{cfg['title']}: 올린 뒤 건수 {n} != 로컬 {len(g)}")
        state[key].update({"title": cfg["title"], "count": n, "updated": date.today().isoformat(), "url": item.homepage})
        print(f"{action}: {cfg['title']} {n}건 → {item.homepage}")

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"항목 ID 저장 → {STATE.relative_to(ROOT)} (공유 범위는 그대로: 소유자만)")


if __name__ == "__main__":
    main()
