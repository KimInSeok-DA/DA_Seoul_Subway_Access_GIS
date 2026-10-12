// 서울 법정동별 지하철 접근성 공개 지도. 데이터는 map/data.js(META, EMD, STATIONS)
(function () {
  // 구간은 ArcGIS 웹맵과 같게: 거리 300/500/800/1,200m
  const METRICS = {
    near_dist_m: {
      title: "가장 가까운 역까지 거리(m)",
      breaks: [300, 500, 800, 1200],
      colors: ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"],
      labels: ["0～300", "300～500", "500～800", "800～1,200", "1,200 초과"],
    },
    cover_500m: {
      title: "역 500m 안 면적 비율(%)",
      breaks: [20, 40, 60, 80],
      colors: ["#f7fcf5", "#c7e9c0", "#74c476", "#31a354", "#006d2c"],
      labels: ["0～20", "20～40", "40～60", "60～80", "80～100"],
    },
    n_station: {
      title: "동 안의 역 수",
      breaks: [1, 2, 3],
      colors: ["#f2f0f7", "#cbc9e2", "#9e9ac8", "#6a51a3"],
      labels: ["0", "1", "2", "3 이상"],
    },
  };
  const fmt = (n) => Number(n).toLocaleString("ko-KR");

  // 값이 구간 경계와 같으면 아래 구간에 넣는다(예: 300은 0～300). 역 수는 정수라 [1,2,3]이 0/1/2/3+가 되도록 미만으로 판단
  function classOf(m, v) {
    const b = METRICS[m].breaks;
    for (let i = 0; i < b.length; i++) {
      if (m === "n_station" ? v < b[i] : v <= b[i]) return i;
    }
    return b.length;
  }

  const map = L.map("map", { zoomControl: true, preferCanvas: true }).setView([37.5665, 126.978], 11);
  // 키가 필요 없는 OpenStreetMap 기본 타일. 단계구분도가 잘 보이도록 CSS로 흑백 처리(style.css)
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> 기여자 | 데이터: 국토교통부·국가철도공단·서울특별시',
  }).addTo(map);

  let metric = "near_dist_m";

  const emdLayer = L.geoJSON(EMD, {
    style: (f) => ({
      fillColor: METRICS[metric].colors[classOf(metric, f.properties[metric])],
      fillOpacity: 0.78,
      color: "#ffffff",
      weight: 0.7,
    }),
    onEachFeature: (f, layer) => {
      const p = f.properties;
      layer.bindPopup(
        `<h3>${p.sgg_nm} ${p.emd_nm}</h3><table>` +
          `<tr><td>가장 가까운 역</td><td>${p.near_station}</td></tr>` +
          `<tr><td>가장 가까운 역까지 거리</td><td>${fmt(p.near_dist_m)}m</td></tr>` +
          `<tr><td>동 안의 역 수</td><td>${p.n_station}개</td></tr>` +
          `<tr><td>역 500m 안 면적 비율</td><td>${p.cover_500m.toFixed(1)}%</td></tr>` +
          `<tr><td>면적</td><td>${p.area_km2.toFixed(2)}㎢</td></tr>` +
          `<tr><td>법정동코드</td><td>${p.bjd_cd}</td></tr></table>`
      );
      layer.on({
        mouseover: (e) => e.target.setStyle({ weight: 2, color: "#1f2933" }),
        mouseout: (e) => emdLayer.resetStyle(e.target),
      });
    },
  }).addTo(map);

  const stationLayer = L.geoJSON(STATIONS, {
    pointToLayer: (f, latlng) =>
      L.circleMarker(latlng, {
        radius: 3.5,
        color: "#ffffff",
        weight: 1,
        fillColor: f.properties.in_seoul ? "#222831" : "#7b8794",
        fillOpacity: 1,
      }),
    onEachFeature: (f, layer) => {
      const p = f.properties;
      layer.bindPopup(
        `<h3>${p.name_full}</h3><table>` +
          `<tr><td>노선</td><td>${p.lines.split(";").join(", ")}</td></tr>` +
          `<tr><td>운영기관</td><td>${p.operators.split(";").join(", ")}</td></tr>` +
          `<tr><td>데이터 기준일</td><td>${p.ref_date || "-"}</td></tr>` +
          `<tr><td>위치</td><td>${p.in_seoul ? "서울 안" : "서울 밖 5km 안"}</td></tr>` +
          (p.coord_fixed ? `<tr><td>좌표</td><td>원본 오류를 서울시 데이터로 보정</td></tr>` : "") +
          `</table>`
      );
    },
  }).addTo(map);

  map.fitBounds(emdLayer.getBounds(), { padding: [10, 10] });

  // 축소하면 역 점이 겹치므로 작게
  const stationRadius = () => (map.getZoom() <= 10 ? 2 : map.getZoom() <= 12 ? 3.5 : 5);
  map.on("zoomend", () => stationLayer.eachLayer((l) => l.setRadius(stationRadius())));
  stationLayer.eachLayer((l) => l.setRadius(stationRadius()));

  function drawLegend() {
    const m = METRICS[metric];
    document.getElementById("legend").innerHTML =
      `<div class="title">${m.title}</div>` +
      m.colors.map((c, i) => `<div class="row"><span class="sw" style="background:${c}"></span>${m.labels[i]}</div>`).join("") +
      `<div class="row"><span class="sw" style="background:#222831;border-radius:50%;width:9px;height:9px;margin:0 6px"></span>지하철역(회색: 서울 밖 5km 안)</div>`;
  }

  document.querySelectorAll('input[name="metric"]').forEach((el) =>
    el.addEventListener("change", (e) => {
      metric = e.target.value;
      emdLayer.setStyle((f) => ({ fillColor: METRICS[metric].colors[classOf(metric, f.properties[metric])] }));
      drawLegend();
    })
  );
  document.getElementById("show-stations").addEventListener("change", (e) => {
    e.target.checked ? stationLayer.addTo(map) : map.removeLayer(stationLayer);
  });

  document.getElementById("n-emd").textContent = META.n_emd;
  document.getElementById("n-st").textContent = META.n_station;
  document.getElementById("collected").textContent = META.collected;
  drawLegend();
})();
