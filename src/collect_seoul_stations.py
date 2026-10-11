"""서울 열린데이터광장 서울시 역사마스터(subwayStationMaster)를 받아 data/raw/에 저장한다.

역 좌표 대조용 두 번째 출처. 받은 건수가 응답의 list_total_count와 같은지 확인한다.
"""
import json
import os
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "seoul_subway_station_master.json"
PAGE = 1000  # 서울 열린데이터광장 API는 한 번에 최대 1,000건


def fetch(key: str, start: int, end: int) -> dict:
    url = f"http://openapi.seoul.go.kr:8088/{key}/json/subwayStationMaster/{start}/{end}/"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    body = r.json()
    if "subwayStationMaster" not in body:
        # 키 오류 등은 최상위 RESULT로 온다. 키가 담긴 URL은 출력하지 않는다
        raise RuntimeError(f"API 오류: {body.get('RESULT', body)}")
    return body["subwayStationMaster"]


def main() -> None:
    load_dotenv(ROOT / ".env")
    key = os.environ["SEOUL_API_KEY"]

    first = fetch(key, 1, PAGE)
    total = first["list_total_count"]
    rows = list(first["row"])
    for start in range(PAGE + 1, total + 1, PAGE):
        rows += fetch(key, start, min(start + PAGE - 1, total))["row"]

    if len(rows) != total:
        raise RuntimeError(f"받은 건수 {len(rows)} != 응답 총건수 {total}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"collected": date.today().isoformat(), "total": total, "rows": rows},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"서울시 역사마스터 {len(rows)}건 저장 → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
