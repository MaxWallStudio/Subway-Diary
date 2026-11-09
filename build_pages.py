"""Build the GitHub Pages copy from the original Flask home template."""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs"


def main() -> None:
    with (ROOT / "stations.csv").open(encoding="cp949", newline="") as source:
        rows = list(csv.reader(source))[1:]

    stations = [
        {
            "id": int(row[0]),
            "line": f"{row[1]}호선",
            "station_number": row[2],
            "name": row[3],
            "latitude": float(row[4]),
            "longitude": float(row[5]),
            "code": row[2],
        }
        for row in rows
    ]
    groups: dict[str, list[dict[str, object]]] = {}
    for station in stations:
        groups.setdefault(str(station["line"]), []).append(station)
    groups = dict(sorted(groups.items(), key=lambda item: int(item[0].replace("호선", ""))))

    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html"]),
    )

    def page_url(endpoint: str, **values: object) -> str:
        if endpoint == "static":
            return "./static/" + str(values.get("filename", ""))
        if endpoint == "station_detail":
            return f"#station-{values['station_id']}"
        if endpoint == "collection":
            return "#collection"
        if endpoint == "profile":
            return "#profile"
        return "./"

    template_source = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    template_source = template_source.replace(
        'class="station-data-item"',
        'class="station-data-item" data-station-id="{{ station[\'id\'] }}"',
    )
    template_source = template_source.replace(
        "const map = L.map(", "window.diaryMap = L.map("
    ).replace(".addTo(map)", ".addTo(window.diaryMap)")
    template_source = template_source.replace("map.fitBounds(", "window.diaryMap.fitBounds(")
    template_source = template_source.replace("map.setView(", "window.diaryMap.setView(")
    template_source = template_source.replace("map.invalidateSize()", "window.diaryMap.invalidateSize()")
    template_source = template_source.replace(
        "        const stationElements =\n            document.querySelectorAll(\".station-data-item\");",
        '''        const localEntries = JSON.parse(localStorage.getItem("station-diary.entries.v1") || "{}");
        document.querySelectorAll(".station-data-item").forEach(item => {
            if (!(localEntries[item.dataset.stationId] || []).length) item.remove();
        });
        const stationElements =
            document.querySelectorAll(".station-data-item");''',
    )
    rendered = env.from_string(template_source).render(
        stations=stations,
        line_groups=groups,
        progress={"visited": 0, "total": len(stations), "progress": 0},
        visited_stations=stations,
        memories_today=[],
        url_for=page_url,
    )
    rendered = rendered.replace(
        "</head>",
        '''<meta name="theme-color" content="#f3f5f7">
<meta name="description" content="지나온 지하철역과 그날의 추억을 기록해 보세요.">
<link rel="manifest" href="./manifest.webmanifest">
<link rel="stylesheet" href="./static/css/pages.css">
<link rel="icon" href="./static/images/diary-icon.svg" type="image/svg+xml">
</head>''',
    )
    rendered = rendered.replace(
        "</body>",
        '<script src="./static/js/diary.js"></script>\n'
        '<script>if("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js").catch(() => {}));</script>\n'
        "</body>",
    )

    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(rendered, encoding="utf-8")
    shutil.copytree(ROOT / "static" / "css", OUT / "static" / "css", dirs_exist_ok=True)
    shutil.copytree(ROOT / "static" / "js", OUT / "static" / "js", dirs_exist_ok=True)
    shutil.copytree(ROOT / "static" / "images", OUT / "static" / "images", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("*.mdp"))
    (OUT / "data").mkdir(exist_ok=True)
    (OUT / "data" / "stations.json").write_text(
        json.dumps(stations, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
