from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    session,
    send_file
)

from database import (
    init_db,
    get_db,
    get_progress,
    get_visited_stations,
    get_stations_with_lines,
    get_memories_today,
    get_station_stats,
    get_profile_stats,
    get_favorite_station,
    set_favorite_station,
    remove_favorite_station,
    get_journey_stats,
    get_report,
    get_station_theme,
    set_station_theme,
    create_user,
    get_user_by_username,
    check_user_password
)

import os
import secrets
import warnings
from pathlib import Path

from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


# =========================================================
# Flask
# =========================================================

app = Flask(__name__)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[]
)

# =========================================================
# 보안 설정
# =========================================================

# 애플리케이션 비밀키는 환경변수로만 받는다.
app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError(
        "FLASK_SECRET_KEY 환경변수가 설정되지 않았습니다."
    )

# 세션 쿠키 보안
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# HTTPS 배포 시 SESSION_COOKIE_SECURE=1로 설정한다.
# 로컬 HTTP 개발환경에서는 기본적으로 꺼져 있다.
app.config["SESSION_COOKIE_SECURE"] = os.environ.get(
    "SESSION_COOKIE_SECURE", "0"
).strip().lower() in {"1", "true", "yes", "on"}


# =========================================================
# 비공개 업로드
# =========================================================

# 사진은 static 폴더에 넣으면 로그인하지 않아도
# /static/... 주소로 직접 접근할 수 있으므로
# static 바깥의 비공개 폴더에 저장한다.

UPLOAD_FOLDER = str(Path(__file__).resolve().with_name("private_uploads"))

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# 업로드 파일 최대 10MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# 허용할 이미지 확장자
ALLOWED_IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "gif",
    "webp"
}

Image.MAX_IMAGE_PIXELS = 20_000_000
IMAGE_FORMATS_BY_EXTENSION = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "gif": "GIF",
    "webp": "WEBP",
}

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


def migrate_old_uploads():
    """
    기존 static/uploads에 저장되어 있던 사진을
    비공개 private_uploads 폴더로 이동한다.

    기존 DB의 visits.photo 값은 파일명만 저장하고 있으므로
    파일명은 그대로 유지한다.
    """
    old_folder = str(Path(__file__).resolve().parent / "static" / "uploads")
    new_folder = app.config["UPLOAD_FOLDER"]

    if not os.path.isdir(old_folder):
        return

    for filename in os.listdir(old_folder):
        old_path = os.path.join(old_folder, filename)
        new_path = os.path.join(new_folder, filename)

        if not os.path.isfile(old_path):
            continue

        # 이미 같은 이름의 파일이 있으면 기존 파일을 건드리지 않는다.
        if os.path.exists(new_path):
            continue

        try:
            os.replace(old_path, new_path)
        except OSError:
            # 파일 하나의 이동 실패 때문에 서버 전체가 중단되지 않도록 한다.
            continue


# =========================================================
# 데이터베이스 초기화
# =========================================================

init_db()

# 기존 공개 업로드 폴더의 사진을 비공개 폴더로 이동
migrate_old_uploads()


# =========================================================
# 로그인 확인
# =========================================================

def is_logged_in():
    user_id = session.get("user_id")
    if user_id is None:
        return False

    # Account deletion also invalidates signed session cookies on other devices.
    conn = get_db()
    try:
        user = conn.execute(
            "SELECT 1 FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
    finally:
        conn.close()

    if not user:
        session.clear()
        return False

    return True

# =========================================================
# CSRF 보호
# =========================================================

def get_csrf_token():

    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)

    return session["csrf_token"]


def validate_csrf_token():

    token = request.form.get("csrf_token")

    if not token:
        data = request.get_json(silent=True)

        if data:
            token = data.get("csrf_token")

    if not token:
        token = request.headers.get("X-CSRF-Token")

    return (
        token
        and token == session.get("csrf_token")
    )


@app.context_processor
def inject_csrf_token():

    return {
        "csrf_token": get_csrf_token()
    }

# =========================================================
# 비공개 사진 제공
# =========================================================

@app.route("/uploads/<path:filename>")
def private_upload(filename):

    # 로그인하지 않은 사용자는 사진에 접근할 수 없다.
    if not is_logged_in():
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # 파일명에 경로가 들어오는 것을 차단한다.
    safe_filename = secure_filename(filename)

    if not safe_filename or safe_filename != filename:
        return "파일을 찾을 수 없습니다.", 404

    conn = get_db()

    # 핵심:
    # 사진 파일명만 확인하지 않고
    # 현재 로그인한 사용자의 방문 기록에 연결된 사진인지 확인한다.
    visit = conn.execute(
        """
        SELECT id
        FROM visits
        WHERE user_id = ?
        AND photo = ?
        LIMIT 1
        """,
        (
            user_id,
            safe_filename
        )
    ).fetchone()

    conn.close()

    if not visit:
        return "파일을 찾을 수 없습니다.", 404

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        safe_filename
    )

    if not os.path.isfile(file_path):
        return "파일을 찾을 수 없습니다.", 404

    response = send_file(
        file_path,
        conditional=True,
        max_age=0
    )
    response.cache_control.private = True
    response.cache_control.no_store = True
    return response


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    return response


# =========================================================
# 역 상세
# =========================================================


@app.route("/station/<int:station_id>")
def station_detail(station_id):

    if not is_logged_in():
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db()

    station = conn.execute(
        """
        SELECT *
        FROM stations
        WHERE id = ?
        """,
        (station_id,)
    ).fetchone()

    if not station:
        conn.close()

        return "역을 찾을 수 없습니다.", 404

    # 현재 로그인한 사용자의 방문 기록만 가져옴
    visits = conn.execute(
        """
        SELECT *
        FROM visits
        WHERE station_id = ?
        AND user_id = ?
        ORDER BY visited_at DESC
        """,
        (
            station_id,
            user_id
        )
    ).fetchall()

    lines = conn.execute(
        """
        SELECT line
        FROM station_lines
        WHERE station_id = ?
        ORDER BY line
        """,
        (station_id,)
    ).fetchall()

    conn.close()

    stats = get_station_stats(
        station_id,
        user_id
    )

    # 사용자별 테마
    theme = get_station_theme(
        user_id,
        station_id
    )
    favorite_station = get_favorite_station(user_id)
    is_favorite = bool(
        favorite_station
        and favorite_station["id"] == station_id
    )

    return render_template(
        "station.html",
        station=station,
        visits=visits,
        lines=lines,
        stats=stats,
        theme=theme,
        is_favorite=is_favorite
    )


# =========================================================
# 방문 기록 추가
# =========================================================

@app.route(
    "/station/<int:station_id>/visit",
    methods=["GET", "POST"]
)
def add_visit(station_id):

    if not is_logged_in():
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db()

    station = conn.execute(
        """
        SELECT *
        FROM stations
        WHERE id = ?
        """,
        (station_id,)
    ).fetchone()

    if not station:
        conn.close()

        return "역을 찾을 수 없습니다.", 404

    if request.method == "POST":

        if not validate_csrf_token():
            return render_template(
                "add_visit.html",
                station=station,
                error="잘못된 요청입니다. 페이지를 새로고침해주세요."
            )


        visited_at = request.form.get(
            "visited_at",
            ""
        )

        emotion = request.form.get(
            "emotion",
            ""
        )

        diary = request.form.get(
            "diary",
            ""
        )

        photo = request.files.get("photo")

        photo_filename = None

        if photo and photo.filename:

            filename = secure_filename(photo.filename)

            if filename:
                extension = filename.rsplit(".", 1)[-1].lower()

                # 허용된 이미지 확장자인지 확인
                if extension not in ALLOWED_IMAGE_EXTENSIONS:
                    conn.close()

                    return render_template(
                        "add_visit.html",
                        station=station,
                        error="JPG, JPEG, PNG, GIF, WEBP 이미지만 업로드할 수 있습니다."
                    )

                # 실제 이미지 파일인지 확인
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", Image.DecompressionBombWarning)
                        image = Image.open(photo)
                        if image.format != IMAGE_FORMATS_BY_EXTENSION[extension]:
                            raise ValueError("Image format does not match extension")
                        if image.width * image.height > Image.MAX_IMAGE_PIXELS:
                            raise ValueError("Image dimensions are too large")
                        image.verify()

                    # 검증 후 파일 포인터를 처음으로 되돌림
                    photo.seek(0)

                except Exception:
                    conn.close()

                    return render_template(
                        "add_visit.html",
                        station=station,
                        error="올바른 이미지 파일만 업로드할 수 있습니다."
                    )

                # 랜덤한 파일명 생성
                random_filename = (
                    secrets.token_hex(16)
                    + "."
                    + extension
                )

                photo_filename = random_filename

                photo.save(
                    os.path.join(
                        app.config["UPLOAD_FOLDER"],
                        random_filename
                    )
                )

        # 반드시 user_id를 함께 저장
        conn.execute(
            """
            INSERT INTO visits (
                user_id,
                station_id,
                visited_at,
                diary,
                emotion,
                photo
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                station_id,
                visited_at,
                diary,
                emotion,
                photo_filename
            )
        )

        conn.commit()
        conn.close()

        return redirect(
            url_for(
                "station_detail",
                station_id=station_id
            )
        )

    conn.close()

    return render_template(
        "add_visit.html",
        station=station
    )


# =========================================================
# 홈
# =========================================================

@app.route("/")
def home():

    if not is_logged_in():
        return redirect(url_for("login"))

    user_id = session["user_id"]

    stations = get_stations_with_lines()

    # -------------------------
    # 노선별 역 그룹 만들기
    # -------------------------

    line_groups = {}

    for station in stations:

        line = station["line"]

        if line not in line_groups:
            line_groups[line] = []

        line_groups[line].append(station)


    # -------------------------
    # 노선 숫자 순서로 정렬
    # -------------------------

    def line_sort_key(line):

        try:
            return int(
                line.replace("호선", "").strip()
            )

        except ValueError:
            return 999


    line_groups = dict(
        sorted(
            line_groups.items(),
            key=lambda item: line_sort_key(item[0])
        )
    )

    progress = get_progress(
        user_id
    )

    visited_stations = get_visited_stations(
        user_id
    )

    memories_today = get_memories_today(
        user_id
    )

    return render_template(
        "index.html",
        stations=stations,
        line_groups=line_groups,
        progress=progress,
        visited_stations=visited_stations,
        memories_today=memories_today
    )


# =========================================================
# 방문 기록 즐겨찾기
# =========================================================

@app.route(
    "/visit/<int:visit_id>/favorite",
    methods=["POST"]
)
def toggle_favorite(visit_id):

    if not is_logged_in():
        return jsonify({
            "error": "로그인이 필요합니다."
        }), 401

    if not validate_csrf_token():
        return jsonify({
            "error": "잘못된 요청입니다."
        }), 403

    user_id = session["user_id"]

    conn = get_db()

    # 핵심:
    # visit_id뿐만 아니라 user_id도 확인한다.
    visit = conn.execute(
        """
        SELECT favorite
        FROM visits
        WHERE id = ?
        AND user_id = ?
        """,
        (
            visit_id,
            user_id
        )
    ).fetchone()

    if not visit:

        conn.close()

        return jsonify({
            "error": "Visit not found"
        }), 404

    new_value = (
        0
        if visit["favorite"]
        else 1
    )

    conn.execute(
        """
        UPDATE visits
        SET favorite = ?
        WHERE id = ?
        AND user_id = ?
        """,
        (
            new_value,
            visit_id,
            user_id
        )
    )

    conn.commit()
    conn.close()

    return jsonify({
        "favorite": new_value
    })


@app.route("/visit/<int:visit_id>/delete", methods=["POST"])
def delete_visit(visit_id):
    if not is_logged_in():
        return jsonify({"error": "로그인이 필요합니다."}), 401

    if not validate_csrf_token():
        return jsonify({"error": "잘못된 요청입니다."}), 403

    user_id = session["user_id"]
    conn = get_db()
    visit = conn.execute(
        "SELECT photo FROM visits WHERE id = ? AND user_id = ?",
        (visit_id, user_id)
    ).fetchone()

    if not visit:
        conn.close()
        return jsonify({"error": "추억을 찾을 수 없습니다."}), 404

    conn.execute(
        "DELETE FROM visits WHERE id = ? AND user_id = ?",
        (visit_id, user_id)
    )
    conn.commit()
    conn.close()

    # 방문 기록을 삭제한 뒤, 다른 기록이 공유하지 않는 사진만 정리합니다.
    photo = visit["photo"]
    if photo:
        conn = get_db()
        still_used = conn.execute(
            "SELECT 1 FROM visits WHERE photo = ? LIMIT 1", (photo,)
        ).fetchone()
        conn.close()
        if not still_used:
            photo_path = os.path.join(app.config["UPLOAD_FOLDER"], photo)
            if os.path.isfile(photo_path):
                try:
                    os.remove(photo_path)
                except OSError:
                    app.logger.warning("Could not remove visit photo %s", photo)

    return jsonify({"success": True})


# =========================================================
# 역 테마 변경
# =========================================================

@app.route(
    "/station/<int:station_id>/theme",
    methods=["POST"]
)
def change_theme(station_id):

    if not is_logged_in():
        return jsonify({
            "error": "로그인이 필요합니다."
        }), 401

    if not validate_csrf_token():
        return jsonify({
            "error": "잘못된 요청입니다."
        }), 403

    user_id = session["user_id"]

    data = request.get_json(
        silent=True
    )

    if not data:
        return jsonify({
            "error": "잘못된 요청입니다."
        }), 400

    theme = data.get("theme")

    allowed_themes = [
        "default",
        "forest",
        "ocean",
        "night",
        "cherry",
        "sunset"
    ]

    if theme not in allowed_themes:
        return jsonify({
            "error": "잘못된 테마입니다."
        }), 400

    conn = get_db()

    station = conn.execute(
        """
        SELECT id
        FROM stations
        WHERE id = ?
        """,
        (station_id,)
    ).fetchone()

    conn.close()

    if not station:
        return jsonify({
            "error": "역을 찾을 수 없습니다."
        }), 404

    # 사용자별 테마 저장
    set_station_theme(
        user_id,
        station_id,
        theme
    )

    return jsonify({
        "success": True
    })


# =========================================================
# 도감
# =========================================================

@app.route("/collection")
def collection():

    if not is_logged_in():
        return redirect(url_for("login"))

    user_id = session["user_id"]

    conn = get_db()

    stations = conn.execute(
        """
        SELECT
            stations.id,
            stations.name,
            stations.latitude,
            stations.longitude,

            GROUP_CONCAT(
                station_lines.line,
                ' · '
            ) AS lines,

            CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM visits
                    WHERE visits.station_id = stations.id
                    AND visits.user_id = ?
                )
                THEN 1
                ELSE 0
            END AS visited

        FROM stations

        LEFT JOIN station_lines
            ON stations.id = station_lines.station_id

        GROUP BY stations.id
        ORDER BY stations.name
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    # 호선별로 역을 묶는다.
    line_groups = {}

    for station in stations:

        lines = station["lines"]

        if not lines:
            continue

        for line in lines.split(" · "):

            if line not in line_groups:
                line_groups[line] = []

            line_groups[line].append(station)

    # 호선 순서 정렬
    def line_sort_key(line):

        try:
            return int(
                line.replace(
                    "호선",
                    ""
                ).strip()
            )

        except ValueError:
            return 999

    line_groups = dict(
        sorted(
            line_groups.items(),
            key=lambda item: line_sort_key(item[0])
        )
    )

    progress = get_progress(
        user_id
    )

    return render_template(
        "collection.html",
        line_groups=line_groups,
        progress=progress
    )


# =========================================================
# 프로필
# =========================================================

@app.route("/profile")
def profile():

    if not is_logged_in():
        return redirect(url_for("login"))

    user_id = session["user_id"]

    stats = get_profile_stats(
        user_id
    )

    favorite_station = get_favorite_station(
        user_id
    )

    return render_template(
        "profile.html",
        stats=stats,
        favorite_station=favorite_station
    )


@app.route("/account/delete", methods=["POST"])
def delete_account():
    if not is_logged_in():
        return redirect(url_for("login"))

    if not validate_csrf_token():
        return "잘못된 요청입니다.", 403

    user_id = session["user_id"]
    authenticated_user = check_user_password(
        session.get("username", ""),
        request.form.get("password", "")
    )

    if not authenticated_user or authenticated_user["id"] != user_id:
        return render_template(
            "profile.html",
            stats=get_profile_stats(user_id),
            favorite_station=get_favorite_station(user_id),
            delete_error=True
        ), 400

    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        photos = conn.execute(
            "SELECT photo FROM visits WHERE user_id = ? AND photo IS NOT NULL",
            (user_id,)
        ).fetchall()
        conn.execute("DELETE FROM visits WHERE user_id = ?", (user_id,))
        conn.execute(
            "DELETE FROM user_station_settings WHERE user_id = ?",
            (user_id,)
        )
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise

    # 사진을 다른 방문 기록이 함께 참조하는 경우 해당 파일은 남겨둡니다.
    upload_root = Path(app.config["UPLOAD_FOLDER"]).resolve()
    for row in photos:
        filename = row["photo"]
        safe_filename = secure_filename(filename)
        if not safe_filename or safe_filename != filename:
            continue

        still_used = conn.execute(
            "SELECT 1 FROM visits WHERE photo = ? LIMIT 1",
            (filename,)
        ).fetchone()
        if still_used:
            continue

        photo_path = (upload_root / filename).resolve()
        if photo_path.parent == upload_root and photo_path.is_file():
            try:
                photo_path.unlink()
            except OSError:
                app.logger.warning("Could not remove deleted account photo %s", filename)

    conn.close()
    session.clear()
    return redirect(url_for("login", account_deleted="1"))


# =========================================================
# 최애역 설정
# =========================================================

@app.route(
    "/station/<int:station_id>/favorite",
    methods=["POST"]
)
def set_favorite(station_id):

    if not is_logged_in():
        return jsonify({
            "error": "로그인이 필요합니다."
        }), 401

    if not validate_csrf_token():
        return jsonify({
            "error": "잘못된 요청입니다."
        }), 403

    user_id = session["user_id"]

    conn = get_db()

    station = conn.execute(
        """
        SELECT id
        FROM stations
        WHERE id = ?
        """,
        (station_id,)
    ).fetchone()

    conn.close()

    if not station:
        return jsonify({
            "error": "역을 찾을 수 없습니다."
        }), 404

    set_favorite_station(
        user_id,
        station_id
    )

    return jsonify({
        "success": True
    })


# =========================================================
# 최애역 삭제
# =========================================================

@app.route(
    "/favorite/remove",
    methods=["POST"]
)
def remove_favorite():

    if not is_logged_in():
        return jsonify({
            "error": "로그인이 필요합니다."
        }), 401

    if not validate_csrf_token():
        return jsonify({
            "error": "잘못된 요청입니다."
        }), 403

    user_id = session["user_id"]

    remove_favorite_station(
        user_id
    )

    return jsonify({
        "success": True
    })


# =========================================================
# 여정
# =========================================================

@app.route("/journey")
def journey():

    if not is_logged_in():
        return redirect(url_for("login"))

    user_id = session["user_id"]

    journey_stats = get_journey_stats(
        user_id
    )

    progress = get_progress(
        user_id
    )

    return render_template(
        "journey.html",
        journey_stats=journey_stats,
        progress=progress
    )


# =========================================================
# 결산
# =========================================================

@app.route("/report")
def report():

    if not is_logged_in():
        return redirect(url_for("login"))

    user_id = session["user_id"]

    year = request.args.get(
        "year",
        type=int
    )

    month = request.args.get(
        "month",
        type=int
    )

    if year is None:
        year = datetime.now().year

    monthly_report = None

    if month is not None:

        monthly_report = get_report(
            user_id,
            year,
            month
        )

    yearly_report = get_report(
        user_id,
        year
    )

    return render_template(
        "report.html",
        year=year,
        month=month,
        monthly_report=monthly_report,
        yearly_report=yearly_report
    )


# =========================================================
# 로그인
# =========================================================

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():

    if request.method == "POST":

        # CSRF 검사
        if not validate_csrf_token():
            return render_template(
                "login.html",
                error="잘못된 요청입니다. 페이지를 새로고침해주세요."
            )

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        user = check_user_password(
            username,
            password
        )

        if user is None:

            return render_template(
                "login.html",
                error="아이디 또는 비밀번호가 올바르지 않습니다."
            )

        # 기존 세션을 완전히 초기화한 후
        # 새로운 로그인 세션 생성
        session.clear()

        session["user_id"] = user["id"]
        session["username"] = user["username"]

        return redirect(
            url_for("home")
        )

    return render_template(
        "login.html",
        account_deleted=request.args.get("account_deleted") == "1"
    )


# =========================================================
# 로그아웃
# =========================================================

@app.route("/logout", methods=["POST"])
def logout():
    if not is_logged_in():
        return redirect(url_for("login"))

    if not validate_csrf_token():
        return jsonify({"error": "잘못된 요청입니다."}), 403

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# 회원가입
# =========================================================

@app.route("/register", methods=["GET", "POST"])
@limiter.limit("3 per day")
def register():

    if request.method == "POST":

        # CSRF 검사
        if not validate_csrf_token():
            return render_template(
                "register.html",
                error="잘못된 요청입니다. 페이지를 새로고침해주세요."
            )

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        privacy_agree = request.form.get(
            "privacy_agree"
        )

        # 기본 입력 확인
        if not username or not password:

            return render_template(
                "register.html",
                error="아이디와 비밀번호를 입력해주세요."
            )

        # 개인정보 처리방침 동의 확인
        if privacy_agree != "on":

            return render_template(
                "register.html",
                error="개인정보 처리방침에 동의해주세요."
            )

        # 아이디 길이
        if len(username) < 3:

            return render_template(
                "register.html",
                error="아이디는 3자 이상이어야 합니다."
            )

        # 비밀번호 길이
        if len(password) < 8:

            return render_template(
                "register.html",
                error="비밀번호는 8자 이상이어야 합니다."
            )

        # 중복 아이디
        if get_user_by_username(username):

            return render_template(
                "register.html",
                error="이미 사용 중인 아이디입니다."
            )

        user_id = create_user(
            username,
            password
        )

        if user_id is None:

            return render_template(
                "register.html",
                error="회원가입에 실패했습니다."
            )

        # 회원가입 직후 자동 로그인
        session.clear()

        session["user_id"] = user_id
        session["username"] = username

        return redirect(
            url_for("home")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# 개인정보 처리방침
# =========================================================

@app.route("/privacy")
def privacy():

    return render_template(
        "privacy.html"
    )


# =========================================================
# 실행
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=False
    )

    
