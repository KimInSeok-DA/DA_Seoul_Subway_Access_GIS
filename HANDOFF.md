# HANDOFF

## 현재 상태 (2026-10-11)

- `main`: PR #1(역 정제·기본 설정), PR #2(경계·지표·검증) 머지됨. 게시·웹맵 캡처는 커밋 전
- 파이프라인 `src/run.py`: 수집 → 정제 → 지표 → 검증까지 동작(37초), 검증 21개 통과
  - 서울 법정동 467개(VWorld WFS), 분석 역 389개(서울 307 + 서울 밖 5km 안 82)
- 데이터 이용 조건 4개 모두 확인(1011_03) → `data/processed/`, `outputs/`도 공개 가능
- ArcGIS Location Platform 무료 계정(`.env`)으로 게시·덮어쓰기 테스트 통과(10-11). `gis.content.add()`는 오류 → `Folder.add()` 사용
- Python: `.venv`(3.12), `requirements.txt`

## 다음 작업

1. 게시 완료(1011_05): `src/publish.py` → 레이어 2개(비공개), 항목 ID는 `outputs/arcgis_items.json`. 덮어쓰기·서버 값 대조 확인
2. 웹맵 완료(사용자 구성, 비공개). Location Platform은 레이어 공개 공유 불가 → 캡처 7장(`docs/images/`)으로 README에 표시, Instant Apps 제외(1011_05). 웹맵 ID `fe76515d51784c36814a5919b0475254`
3. 확장: GeoPackage·Shapefile·CSV 출력 → PostGIS(Docker) 교차 검증 → Routing 도보 거리 비교 → GitHub Pages 정적 지도(1011_01). **GitHub Pages가 유일한 공개 링크라 우선순위를 올림**
4. README 공개 링크·스크린샷·회고

## 결정 기록

- 1011_01 작업 범위(Web Scene 제외: PC에서 하드웨어 가속 불가)
- 1011_02 역 정제 규칙
- 1011_03 데이터 이용 조건과 법정동 경계
- 1011_04 지표와 검증

## 열린 결정

- 일정 문서의 요일이 하루씩 어긋나 있음(10-11은 일요일, 마감 10-18은 일요일)
