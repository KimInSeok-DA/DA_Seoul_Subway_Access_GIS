"""전체 파이프라인: 수집 → 정제 → 지표 → 검증 → (선택) 업로드.

    python src/run.py              # 업로드 없이 검증까지
    python src/run.py --skip-collect   # API 다시 부르지 않고 data/raw/ 캐시로
    python src/run.py --publish    # 검증을 통과했을 때만 ArcGIS Online 레이어 갱신
"""
import argparse
import sys
from datetime import datetime

import build_stations
import collect_boundaries
import collect_seoul_stations
import compute_metrics
import validate


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-collect", action="store_true", help="API 수집을 건너뛰고 data/raw/ 캐시 사용")
    ap.add_argument("--publish", action="store_true", help="검증 통과 시 ArcGIS Online 업로드")
    args = ap.parse_args()

    print(f"실행 시작 {datetime.now():%Y-%m-%d %H:%M:%S}")
    if not args.skip_collect:
        collect_seoul_stations.main()
        collect_boundaries.main()
    build_stations.main()
    compute_metrics.main()

    if validate.main() != 0:
        print("검증 실패 → 업로드하지 않고 멈춤")
        return 1

    if args.publish:
        import publish  # 업로드할 때만 arcgis를 불러온다(불러오는 데 시간이 걸림)
        publish.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
