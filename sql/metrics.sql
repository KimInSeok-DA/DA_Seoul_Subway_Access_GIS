-- 법정동별 지하철 접근성 지표를 PostGIS로 다시 계산한다(Python compute_metrics.py와 독립).
-- 입력: emd(법정동 경계, EPSG:4326), stations(정제된 전체 역 942개, EPSG:4326)
-- 거리·면적은 EPSG:5179(m)로 변환해서 계산한다.

DROP TABLE IF EXISTS emd_m, st_m, metrics_sql;

-- 1) 투영 좌표계로 변환
CREATE TABLE emd_m AS
SELECT bjd_cd, emd_nm, ST_Transform(geom, 5179) AS geom
FROM emd;

-- 2) 서울 경계 + 5km 안의 역만(필터도 SQL에서 다시 함)
CREATE TABLE st_m AS
WITH seoul AS (SELECT ST_Union(geom) AS geom FROM emd_m)
SELECT s.station_id, s.name, ST_Transform(s.geom, 5179) AS geom
FROM stations s, seoul
WHERE ST_DWithin(ST_Transform(s.geom, 5179), seoul.geom, 5000);

CREATE INDEX ON st_m USING GIST (geom);
CREATE INDEX ON emd_m USING GIST (geom);

-- 3) 지표
CREATE TABLE metrics_sql AS
WITH cover AS (                                   -- 역 500m 반경의 합집합(원을 16분할: shapely 기본값과 같게)
  SELECT ST_Union(ST_Buffer(geom, 500, 'quad_segs=16')) AS geom FROM st_m
)
SELECT
  e.bjd_cd,
  e.emd_nm,
  nn.name                                          AS near_station,
  ROUND(nn.dist)::int                              AS near_dist_m,
  (SELECT COUNT(*) FROM st_m s WHERE ST_Within(s.geom, e.geom))::int AS n_station,
  ROUND((ST_Area(ST_Intersection(e.geom, c.geom)) / ST_Area(e.geom) * 100)::numeric, 1) AS cover_500m
FROM emd_m e
CROSS JOIN cover c
CROSS JOIN LATERAL (                              -- 대표점(폴리곤 안의 점)에서 가장 가까운 역: KNN 인덱스(<->)
  SELECT s.name, ST_Distance(ST_PointOnSurface(e.geom), s.geom) AS dist
  FROM st_m s
  ORDER BY ST_PointOnSurface(e.geom) <-> s.geom
  LIMIT 1
) nn;
