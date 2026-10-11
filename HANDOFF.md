# HANDOFF

## 현재 상태 (2026-10-11)

- GitHub 원격 연결, README만 커밋·푸시됨. 나머지 파일은 아직 커밋 전
- ArcGIS Location Platform 무료 계정(`.env`)으로 로그인·Feature Layer 게시·덮어쓰기·삭제 테스트 통과
- Python: `.venv`(3.12), `arcgis 2.4.3`, `python-dotenv`

## 다음 작업

1. 브라우저 확인 결과(10-11): Map Viewer 열림. Scene Viewer는 하드웨어 가속이 필요한데 사용자 PC에서 켜면 블루스크린이 나서 쓰지 않음 → Web Scene은 범위에서 뺌. Instant Apps는 관리 화면 대신 예시 앱이 열려, 웹맵 저장 후 Map Viewer의 "앱 만들기"에서 다시 확인
2. 범위: `docs/의사결정/1011_01_작업범위.md` (핵심 + WFS·다중 포맷 + PostGIS 교차 검증 + Routing 비교)
3. 역 정제 완료(10-11): `src/collect_seoul_stations.py`, `src/build_stations.py` → 역 943개, 좌표 보정 5행. 규칙은 `docs/의사결정/1011_02_역_정제_규칙.md`
   다음: VWorld 법정동 경계 WFS 수집·이용 조건 확인 → 서울+5km 역 필터 → 지표 계산 → 검증
4. 업로드·덮어쓰기 → Web Map → Instant Apps → 항목 정보(요약·설명·출처·이용 조건·기준일·태그)

## 열린 결정

- `AGENTS.md`, `docs/AI_활용_기록.md`의 지원 맥락 문장을 공개 전에 고칠지, `AGENTS.md`·`CLAUDE.md`를 공개 저장소에서 뺄지
- 일정 문서의 요일이 하루씩 어긋나 있음(10-11은 일요일, 마감 10-18은 일요일)
