# HANDOFF

## 현재 상태 (2026-10-12)

- 계획한 작업 완료: 수집·정제·지표·검증 → ArcGIS 게시·웹맵 → 공개 지도 → 다중 포맷 → PostGIS 교차 검증 → 도보 거리 비교 → 마무리(README 정리·회고)
- `main`: PR #1～#8 머지. 마무리(README·AGENTS 정리, 출력 줄바꿈 고정, numpy 명시)는 커밋 전
- 공개 지도: https://kiminseok-da.github.io/DA_Seoul_Subway_Access_GIS/ (Pages: main, /docs)
- ArcGIS(Location Platform 무료, 항목 5개 모두 비공개): 레이어 2개 `outputs/arcgis_items.json`, 웹맵 `fe76515d51784c36814a5919b0475254`. 레이어 공개 공유는 제품 제한으로 불가(1011_05)
- 실행: `src/run.py`(수집 포함 약 50초), 검증 21개 통과. 새로 받은 폴더에서 API부터 다시 수집해도 결과가 같음(수집일만 다름, 10-12 확인)
- Python: `.venv`(3.12), `requirements.txt`

## 다시 돌릴 때

- 역 원본 xlsx는 저장소에 없음 → README "실행 > 준비"
- 수집부터 다시 돌리면 경계 수집일(`collected`)이 바뀌어 `data/processed`·`docs/map/data.js`·`docs/downloads` 파일이 바뀐다(내용은 같고 날짜만). 공개본을 갱신하려면 커밋·푸시하고, ArcGIS도 맞추려면 `--publish`
- `routing_compare.py`를 옵션 없이 돌리면 ArcGIS 경로 서비스를 약 1,400건 쓴다(무료 월 20,000건). 요약만 다시 만들 때는 `--from-raw`

## 결정 기록

- 1011_01 작업 범위(Web Scene 제외: PC에서 하드웨어 가속 불가)
- 1011_02 역 정제 규칙
- 1011_03 데이터 이용 조건과 법정동 경계
- 1011_04 지표와 검증
- 1011_05 ArcGIS 게시(FGDB, 공개 공유 불가)
- 1012_01 공개 지도(GitHub Pages, Leaflet, 단순화 1m)
- 1012_02 다중 포맷(GPKG·Shapefile·CSV, 파일 날짜 고정)
- 1012_03 PostGIS 교차 검증
- 1012_04 도보 거리 비교(ArcGIS 경로 서비스)

## 작업 규칙(사용자 지적)

- 커밋·푸시는 사용자가 요청할 때만. "진행해"는 작업 진행만 뜻함
- 단계를 넘기기 전에 독립 재검증

## 열린 결정

- README 회고 문장은 작성자 관점 초안 → 사용자가 표현 확인
- `_private/02_로드맵.md` 일정표의 요일 표기 정정 여부(10-11은 일요일, 마감 10-18은 일요일)
