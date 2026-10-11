# HANDOFF

## 현재 상태 (2026-10-11)

- `main`: PR #1(역 정제·기본 설정) 머지됨. 이후 작업(경계·지표·검증·run.py)은 아직 커밋 전
- 파이프라인 `src/run.py`: 수집 → 정제 → 지표 → 검증까지 동작(37초), 검증 21개 통과
  - 서울 법정동 467개(VWorld WFS), 분석 역 389개(서울 307 + 서울 밖 5km 안 82)
- 데이터 이용 조건 4개 모두 확인(1011_03) → `data/processed/`, `outputs/`도 공개 가능
- ArcGIS Location Platform 무료 계정(`.env`)으로 게시·덮어쓰기 테스트 통과(10-11). `gis.content.add()`는 오류 → `Folder.add()` 사용
- Python: `.venv`(3.12), `requirements.txt`

## 다음 작업

1. `src/publish.py`: 법정동 지표·역 레이어 2개를 Hosted Feature Layer로 게시, 이후 덮어쓰기. 항목 정보(요약·설명·출처·이용 조건·기준일·태그·credits)를 코드로. 덮어쓰기 직후 건수 조회는 다시 시도 필요
2. Map Viewer로 Web Map(단계구분도 + 역 점 + 팝업) → Instant Apps 가능 여부 확인(Map Viewer "앱 만들기")
3. 확장: GeoPackage·Shapefile·CSV 출력 → PostGIS(Docker) 교차 검증 → Routing 도보 거리 비교 → GitHub Pages 정적 지도(1011_01)
4. README 공개 링크·스크린샷·회고

## 결정 기록

- 1011_01 작업 범위(Web Scene 제외: PC에서 하드웨어 가속 불가)
- 1011_02 역 정제 규칙
- 1011_03 데이터 이용 조건과 법정동 경계
- 1011_04 지표와 검증

## 열린 결정

- 일정 문서의 요일이 하루씩 어긋나 있음(10-11은 일요일, 마감 10-18은 일요일)
