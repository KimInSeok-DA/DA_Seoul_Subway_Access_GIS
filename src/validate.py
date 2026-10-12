"""결과 데이터를 검증하고 outputs/validation_report.md를 쓴다. 하나라도 실패하면 종료 코드 1(업로드 금지).

검사: 건수·코드, 도형·좌표계, 좌표 범위, 역 좌표 겹침, 역 주소의 법정동 대조, 지표 상식, 최신성
"""
import re
import sys
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
CODES = ROOT / "data" / "reference" / "법정동코드_국토교통부_20260630.csv"
REPORT = ROOT / "outputs" / "validation_report.md"

CRS_M = 5179
BUFFER_M = 5000          # compute_metrics의 서울 밖 역 범위
COLLIDE_M = 50           # 이름이 다른 역이 이만큼 가까우면 좌표 복사 오류 의심
SAME_LINE_M = 300        # 같은 노선의 다른 역이 이만큼 가까우면 같은 역 이중 집계 의심
ADDR_DONG_MAX_M = 200    # 역 점과 주소에 적힌 법정동 경계 사이 허용 거리
SEOUL_BOX = (126.70, 37.38, 127.25, 37.75)   # 서울 + 완충의 대략 범위(경도·위도)

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    results.append((name, bool(ok), detail))


def addr_dongs(addresses: str) -> set[tuple[str, str]]:
    """'서울특별시 강남구 ... (삼성동)' → {('강남구', '삼성동')}. 괄호 안 법정동만 쓴다"""
    out = set()
    for addr in (addresses or "").split(" | "):
        gu = re.search(r"서울\S*\s+(\S+구)", addr)
        if not gu:
            continue
        for m in re.findall(r"\(([^)]*)\)", addr):
            for part in re.split(r"[,·\s]+", m):
                if re.fullmatch(r"[가-힣]+[0-9]*(동|가)", part) and len(part) > 2:
                    out.add((gu.group(1), part))
    return out


def main() -> int:
    emd = gpd.read_file(P / "seoul_emd.geojson")
    met = gpd.read_file(P / "seoul_emd_metrics.geojson")
    st = gpd.read_file(P / "stations_study.geojson")
    codes = pd.read_csv(CODES, dtype=str, encoding="utf-8-sig")
    seoul_codes = codes[codes["법정동코드"].str.startswith("11") & codes["읍면동명"].notna() & codes["리명"].isna()]

    # 1) 건수·코드
    check("경계 수 = 법정동코드 표의 서울 법정동 수", len(emd) == len(seoul_codes), f"{len(emd)} / {len(seoul_codes)}")
    check("법정동코드 중복 0", not met["bjd_cd"].duplicated().any(), f"중복 {met['bjd_cd'].duplicated().sum()}")
    check("법정동코드 집합 일치", set(met["bjd_cd"]) == set(seoul_codes["법정동코드"]),
          f"차이 {len(set(met['bjd_cd']) ^ set(seoul_codes['법정동코드']))}")
    check("지표 행 수 = 경계 수(조인 손실 없음)", len(met) == len(emd), f"{len(met)} / {len(emd)}")

    # 2) 도형·좌표계
    for nm, g in (("법정동 지표", met), ("역", st)):
        check(f"{nm}: 좌표계 EPSG:4326", g.crs is not None and g.crs.to_epsg() == 4326, str(g.crs))
        check(f"{nm}: 빈 도형 0", not g.is_empty.any(), f"{g.is_empty.sum()}")
        check(f"{nm}: 유효하지 않은 도형 0", g.is_valid.all(), f"{(~g.is_valid).sum()}")

    # 3) 좌표 범위(위도·경도 뒤바뀜 포함)
    x0, y0, x1, y1 = SEOUL_BOX
    b = met.total_bounds
    check("법정동 경계가 서울 범위 안", x0 <= b[0] and y0 <= b[1] and b[2] <= x1 and b[3] <= y1, f"bounds {b.round(4).tolist()}")
    out_box = (~st.geometry.x.between(x0, x1) | ~st.geometry.y.between(y0, y1)).sum()
    check("역 좌표가 서울+완충 범위 안", out_box == 0, f"범위 밖 {out_box}")

    # 4) 이름이 다른 역이 거의 같은 자리(좌표 복사 오류)
    sm = st.to_crs(CRS_M)
    near = gpd.sjoin_nearest(sm[["name", "geometry"]], sm[["name", "geometry"]], distance_col="d",
                             exclusive=True, how="inner")
    coll = near[(near["d"] < COLLIDE_M) & (near["name_left"] != near["name_right"])]
    check(f"이름이 다른 역이 {COLLIDE_M}m 안에 겹치지 않음", coll.empty,
          "; ".join(f"{a}↔{c} {d:.0f}m" for a, c, d in coll[["name_left", "name_right", "d"]].values) or "0쌍")

    # 4-2) 같은 노선을 지나는데 이름이 다른 역이 아주 가까움(같은 역이 두 번 세어짐)
    near2 = gpd.sjoin_nearest(sm[["name", "lines", "geometry"]], sm[["name", "lines", "geometry"]],
                              distance_col="d", exclusive=True, how="inner")
    dup = [f"{r.name_left}↔{r.name_right} {r.d:.0f}m" for r in near2.itertuples()
           if r.d < SAME_LINE_M and r.name_left < r.name_right
           and set(r.lines_left.split(";")) & set(r.lines_right.split(";"))]
    check(f"같은 노선의 이름이 다른 역이 {SAME_LINE_M}m 안에 없음(이중 집계)", not dup, "; ".join(dup) or "0쌍")

    # 5) 역 주소의 법정동과 실제 위치 대조(기준점 검사)
    e5 = emd.to_crs(CRS_M)
    dists, missing, bad = [], 0, []
    for r in sm[sm["in_seoul"]].itertuples():
        for gu, dong in addr_dongs(r.addresses):
            poly = e5[(e5["sgg_nm"] == gu) & (e5["emd_nm"] == dong)]
            if poly.empty:
                missing += 1  # 행정동 이름 등 법정동이 아닌 표기
                continue
            d = poly.distance(r.geometry).min()
            dists.append(d)
            if d > ADDR_DONG_MAX_M:
                bad.append(f"{r.name}({gu} {dong}) {d:.0f}m")
    check(f"역 주소의 법정동 경계에서 {ADDR_DONG_MAX_M}m 안", not bad and len(dists) > 100,
          f"대조 {len(dists)}쌍, 경계 안 {sum(d == 0 for d in dists)}쌍, 최대 {max(dists):.0f}m, 법정동 아님 {missing}건"
          + (f", 실패: {'; '.join(bad)}" if bad else ""))

    # 6) 지표 상식
    check("cover_500m가 0～100", met["cover_500m"].between(0, 100).all(),
          f"{met['cover_500m'].min()}～{met['cover_500m'].max()}")
    check("near_dist_m가 0 이상, 완충 거리 미만(서울 밖 역 누락 없음)",
          met["near_dist_m"].between(0, BUFFER_M - 1).all(), f"최대 {met['near_dist_m'].max()}m < {BUFFER_M}m")
    has_st = met[met["n_station"] > 0]
    check("역이 있는 동은 cover_500m > 0", (has_st["cover_500m"] > 0).all(), f"역 있는 동 {len(has_st)}개")
    check("동 안 역 수 합 = 서울 안 역 수", met["n_station"].sum() == st["in_seoul"].sum(),
          f"{met['n_station'].sum()} / {st['in_seoul'].sum()}")

    # 7) 최신성
    check("경계 수집일 기록", met["collected"].notna().all(), f"{str(met['collected'].iloc[0])[:10]}")
    check("역 기준일 기록(역마다 최근 행 기준)", st["ref_date"].notna().mean() > 0.95,
          f"기준일 있는 역 {st['ref_date'].notna().sum()}/{len(st)}, 범위 {str(st['ref_date'].min())[:10]}～{str(st['ref_date'].max())[:10]}")

    # 리포트
    n_fail = sum(not ok for _, ok, _ in results)
    lines = [
        "# 검증 리포트", "",
        f"- 실행: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 결과: **{'통과' if n_fail == 0 else f'실패 {n_fail}건'}** ({len(results)}개 검사)", "",
        "| 검사 | 결과 | 내용 |", "|---|---|---|",
    ] + [f"| {n} | {'통과' if ok else '**실패**'} | {d} |" for n, ok, d in results]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    for n, ok, d in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {n} — {d}")
    print(f"\n{'검증 통과' if n_fail == 0 else f'검증 실패 {n_fail}건 — 업로드하지 않음'} → {REPORT.relative_to(ROOT)}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
