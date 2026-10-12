# 1012_03 PostGIS 교차 검증

## 왜

Python(geopandas·shapely) 한 가지 방법으로만 계산하면 정의를 잘못 코드로 옮긴 실수를 같은 방식의 검사로는 놓칠 수 있다. 같은 원본으로 **SQL(PostGIS)로 다시 계산**해 대조한다.

## 방법

- `docker-compose.yml`: `postgis/postgis:16-3.4`, 이 PC에서만 접속(127.0.0.1:5433), 비밀번호는 `.env`의 `POSTGIS_PASSWORD`
- 입력은 원본 경계(`seoul_emd.geojson`)와 정제된 **전체** 역(`stations.geojson`, 942개)만 넣는다. Python 지표 결과나 서울+5km 필터 결과는 넣지 않는다
- `sql/metrics.sql`
  - `ST_Transform(geom, 5179)`로 투영
  - 서울+5km 필터: `ST_DWithin(역, ST_Union(동), 5000)`
  - 최근접: `ST_PointOnSurface`(대표점) + KNN 인덱스 `<->` + `ST_Distance`
  - 역 수: `ST_Within`
  - 500m 면적 비율: `ST_Union(ST_Buffer(역, 500, 'quad_segs=16'))`와 `ST_Intersection`의 면적
- `src/crosscheck_postgis.py`: 결과 대조, `outputs/postgis_crosscheck.md` 작성. Docker가 필요해서 `run.py`에는 넣지 않은 별도 검증
- 허용 오차: 거리 1m(정수 반올림), 비율 0.1%p(소수 1자리 반올림), 역 수·최근접 역 이름은 같아야 함

## 결과 (실제 실행, PostGIS 3.4.3, SQL 3.6초)

- 법정동 467/467, 서울+5km 역 389(Python과 같음)
- 최근접 역 이름 불일치 0, 거리 차이 최대 0m, 역 수 불일치 0, 면적 비율 차이 최대 0.0%p — **467개 동 모두 완전 일치**

## 완전 일치를 믿어도 되는가 (음성 시험)

- 버퍼 원의 분할 수만 16 → 8(PostGIS 기본값)로 바꾸면 467개 중 **251개 동이 0.1%p 넘게 달라짐**(최대 1.1%p). 비교가 작은 차이도 잡는다
- 따라서 일치는 비교가 무뎌서가 아니라 두 구현이 같은 정의(대표점·5km 필터·500m 원)로 같은 값을 냈다는 뜻이다. 둘 다 GEOS·PROJ를 쓰므로 정의가 같으면 값도 같은 것이 정상
- 반대로 원 분할처럼 **정의의 작은 차이가 결과를 바꾼다**는 것도 확인했다. 그래서 `metrics.sql`에 `quad_segs=16`을 명시했다

## 바꾸는 조건

- 지표 정의(대표점·반경·필터)를 바꾸면 `compute_metrics.py`와 `metrics.sql`을 같이 고치고 이 교차 검증을 다시 돌린다
