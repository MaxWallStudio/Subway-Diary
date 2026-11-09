import sqlite3
import math
from pathlib import Path

from datetime import datetime
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


DB_NAME = str(Path(__file__).resolve().with_name("station_diary.db"))


# =========================================================
# DB 연결
# =========================================================

def get_db():

    conn = sqlite3.connect(DB_NAME)

    conn.row_factory = sqlite3.Row

    return conn


# =========================================================
# DB 초기화
# =========================================================

def init_db():

    conn = get_db()

    # -----------------------------------------------------
    # 사용자
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            favorite_station_id INTEGER
        )
    """)

    # -----------------------------------------------------
    # 역
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            station_number TEXT,
            latitude REAL,
            longitude REAL,
            is_favorite INTEGER DEFAULT 0,
            theme TEXT DEFAULT 'default'
        )
    """)

    # -----------------------------------------------------
    # 기존 DB에 theme이 없는 경우
    # -----------------------------------------------------

    try:

        conn.execute("""
            ALTER TABLE stations
            ADD COLUMN theme TEXT DEFAULT 'default'
        """)

    except sqlite3.OperationalError:
        pass


    try:

        conn.execute("""
            ALTER TABLE stations
            ADD COLUMN station_number TEXT
        """)

    except sqlite3.OperationalError:
        pass
    # -----------------------------------------------------
    # 기존 DB에 is_favorite이 없는 경우
    # -----------------------------------------------------

    try:

        conn.execute("""
            ALTER TABLE stations
            ADD COLUMN is_favorite INTEGER DEFAULT 0
        """)

    except sqlite3.OperationalError:
        pass

    # -----------------------------------------------------
    # 기존 users에 favorite_station_id가 없는 경우
    # -----------------------------------------------------

    try:

        conn.execute("""
            ALTER TABLE users
            ADD COLUMN favorite_station_id INTEGER
        """)

    except sqlite3.OperationalError:
        pass

    # -----------------------------------------------------
    # 역과 노선 연결
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS station_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id INTEGER NOT NULL,
            line TEXT NOT NULL,
            station_number TEXT,
            FOREIGN KEY (station_id)
                REFERENCES stations(id)
        )
    """)

    try:
        conn.execute("""
            ALTER TABLE station_lines
            ADD COLUMN station_number TEXT
        """)
    except sqlite3.OperationalError:
        pass

    # -----------------------------------------------------
    # 방문 기록
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            station_id INTEGER NOT NULL,
            visited_at TEXT NOT NULL,
            diary TEXT,
            emotion TEXT,
            favorite INTEGER DEFAULT 0,
            photo TEXT,
            theme TEXT,
            FOREIGN KEY (user_id)
                REFERENCES users(id),
            FOREIGN KEY (station_id)
                REFERENCES stations(id)
        )
    """)

    # -----------------------------------------------------
    # 기존 visits에 user_id가 없는 경우
    # -----------------------------------------------------

    try:

        conn.execute("""
            ALTER TABLE visits
            ADD COLUMN user_id INTEGER
        """)

    except sqlite3.OperationalError:
        pass

    # -----------------------------------------------------
    # 사용자별 역 설정
    #
    # 최애역이나 테마처럼
    # "역 자체의 정보가 아니라 사용자의 설정"을 저장
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_station_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            station_id INTEGER NOT NULL,
            theme TEXT DEFAULT 'default',

            UNIQUE(user_id, station_id),

            FOREIGN KEY (user_id)
                REFERENCES users(id),

            FOREIGN KEY (station_id)
                REFERENCES stations(id)
        )
    """)

    conn.commit()

    conn.close()


# =========================================================
# 역 추가 / 수정
# =========================================================

def add_or_update_station(
    name,
    line,
    station_number,
    latitude,
    longitude
):

    conn = get_db()

    station = conn.execute("""
        SELECT id
        FROM stations
        WHERE name = ?
    """, (name,)).fetchone()

    if station:

        station_id = station["id"]

        conn.execute("""
            UPDATE stations
            SET latitude = ?,
                longitude = ?
            WHERE id = ?
        """, (
            latitude,
            longitude,
            station_id
        ))

    else:

        cursor = conn.execute("""
            INSERT INTO stations (
                name,
                latitude,
                longitude
            )
            VALUES (?, ?, ?)
        """, (
            name,
            latitude,
            longitude
        ))

        station_id = cursor.lastrowid

    line_exists = conn.execute("""
        SELECT id
        FROM station_lines
        WHERE station_id = ?
        AND line = ?
    """, (
        station_id,
        line
    )).fetchone()

    if line_exists:

        conn.execute("""
            UPDATE station_lines
            SET station_number = ?
            WHERE id = ?
        """, (
            station_number,
            line_exists["id"]
        ))

    else:

        conn.execute("""
            INSERT INTO station_lines (
                station_id,
                line,
                station_number
            )
            VALUES (?, ?, ?)
        """, (
            station_id,
            line,
            station_number
        ))

    conn.commit()

    conn.close()


# =========================================================
# 전체 역
# =========================================================

def get_stations():

    conn = get_db()

    stations = conn.execute("""
        SELECT *
        FROM stations
        ORDER BY name
    """).fetchall()

    conn.close()

    return stations


# =========================================================
# 역의 노선
# =========================================================

def get_station_lines(station_id):

    conn = get_db()

    lines = conn.execute("""
        SELECT line
        FROM station_lines
        WHERE station_id = ?
        ORDER BY line
    """, (station_id,)).fetchall()

    conn.close()

    return lines


# =========================================================
# 전체 역 + 노선
# =========================================================

def get_stations_with_lines():

    conn = get_db()

    stations = conn.execute("""
        SELECT
            stations.id,
            stations.name,
            stations.latitude,
            stations.longitude,
            stations.theme,
            station_lines.line,
            station_lines.station_number
        FROM stations

        LEFT JOIN station_lines
            ON stations.id = station_lines.station_id

        ORDER BY stations.name
    """).fetchall()

    conn.close()

    return stations


# =========================================================
# 진행률
# =========================================================

def get_progress(user_id):

    conn = get_db()

    total_stations = conn.execute("""
        SELECT COUNT(*)
        FROM stations
    """).fetchone()[0]

    visited_stations = conn.execute("""
        SELECT COUNT(DISTINCT station_id)
        FROM visits
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

    conn.close()

    progress = (
        visited_stations / total_stations * 100
        if total_stations
        else 0
    )

    return {
        "total": total_stations,
        "visited": visited_stations,
        "progress": progress
    }


# =========================================================
# 방문한 역
# =========================================================

def get_visited_stations(user_id):

    conn = get_db()

    stations = conn.execute("""
        SELECT DISTINCT
            stations.id,
            stations.name,
            stations.latitude,
            stations.longitude
        FROM stations

        INNER JOIN visits
            ON stations.id = visits.station_id

        WHERE visits.user_id = ?

        AND stations.latitude IS NOT NULL
        AND stations.longitude IS NOT NULL
    """, (user_id,)).fetchall()

    conn.close()

    return stations


# =========================================================
# 오늘의 추억
# =========================================================

def get_memories_today(user_id):

    conn = get_db()

    today = datetime.now().strftime("%m-%d")

    memories = conn.execute("""
        SELECT
            visits.id,
            visits.visited_at,
            visits.diary,
            visits.emotion,
            visits.photo,

            stations.id AS station_id,
            stations.name AS station_name

        FROM visits

        INNER JOIN stations
            ON visits.station_id = stations.id

        WHERE visits.user_id = ?

        AND substr(
            visits.visited_at,
            6,
            5
        ) = ?

        ORDER BY visits.visited_at DESC
    """, (
        user_id,
        today
    )).fetchall()

    conn.close()

    return memories


# =========================================================
# 특정 역의 방문 통계
# =========================================================

def get_station_stats(
    station_id,
    user_id
):

    conn = get_db()

    stats = conn.execute("""
        SELECT
            COUNT(*) AS visit_count,
            MIN(visited_at) AS first_visit,
            MAX(visited_at) AS last_visit

        FROM visits

        WHERE station_id = ?
        AND user_id = ?
    """, (
        station_id,
        user_id
    )).fetchone()

    conn.close()

    return stats


# =========================================================
# 도감 통계
# =========================================================

def get_collection_stats(user_id):

    conn = get_db()

    total = conn.execute("""
        SELECT COUNT(*)
        FROM stations
    """).fetchone()[0]

    visited = conn.execute("""
        SELECT COUNT(DISTINCT station_id)
        FROM visits
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

    conn.close()

    return {
        "total": total,
        "visited": visited,
        "progress": (
            visited / total * 100
            if total
            else 0
        )
    }


# =========================================================
# 프로필 통계
# =========================================================

def get_profile_stats(user_id):

    conn = get_db()

    visited_stations = conn.execute("""
        SELECT COUNT(DISTINCT station_id)
        FROM visits
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

    total_visits = conn.execute("""
        SELECT COUNT(*)
        FROM visits
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

    total_photos = conn.execute("""
        SELECT COUNT(*)
        FROM visits
        WHERE user_id = ?
        AND photo IS NOT NULL
        AND photo != ''
    """, (user_id,)).fetchone()[0]

    total_memories = conn.execute("""
        SELECT COUNT(*)
        FROM visits
        WHERE user_id = ?
        AND diary IS NOT NULL
        AND diary != ''
    """, (user_id,)).fetchone()[0]

    first_visit = conn.execute("""
        SELECT MIN(visited_at)
        FROM visits
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

    last_visit = conn.execute("""
        SELECT MAX(visited_at)
        FROM visits
        WHERE user_id = ?
    """, (user_id,)).fetchone()[0]

    conn.close()

    return {
        "visited_stations": visited_stations,
        "total_visits": total_visits,
        "total_photos": total_photos,
        "total_memories": total_memories,
        "first_visit": first_visit,
        "last_visit": last_visit
    }


# =========================================================
# 최애역 가져오기
# =========================================================

def get_favorite_station(user_id):

    conn = get_db()

    station = conn.execute("""
        SELECT stations.*
        FROM users

        INNER JOIN stations
            ON users.favorite_station_id = stations.id

        WHERE users.id = ?
    """, (user_id,)).fetchone()

    conn.close()

    return station


# =========================================================
# 최애역 설정
# =========================================================

def set_favorite_station(
    user_id,
    station_id
):

    conn = get_db()

    conn.execute("""
        UPDATE users
        SET favorite_station_id = ?
        WHERE id = ?
    """, (
        station_id,
        user_id
    ))

    conn.commit()

    conn.close()


# =========================================================
# 최애역 삭제
# =========================================================

def remove_favorite_station(user_id):

    conn = get_db()

    conn.execute("""
        UPDATE users
        SET favorite_station_id = NULL
        WHERE id = ?
    """, (user_id,))

    conn.commit()

    conn.close()


# =========================================================
# 사용자별 역 테마
# =========================================================

def get_station_theme(
    user_id,
    station_id
):

    conn = get_db()

    setting = conn.execute("""
        SELECT theme
        FROM user_station_settings

        WHERE user_id = ?
        AND station_id = ?
    """, (
        user_id,
        station_id
    )).fetchone()

    conn.close()

    if setting:
        return setting["theme"]

    return "default"


# =========================================================
# 사용자별 역 테마 변경
# =========================================================

def set_station_theme(
    user_id,
    station_id,
    theme
):

    conn = get_db()

    conn.execute("""
        INSERT INTO user_station_settings (
            user_id,
            station_id,
            theme
        )
        VALUES (?, ?, ?)

        ON CONFLICT(user_id, station_id)
        DO UPDATE SET
            theme = excluded.theme
    """, (
        user_id,
        station_id,
        theme
    ))

    conn.commit()

    conn.close()


# =========================================================
# 두 좌표 사이 거리
# =========================================================

def calculate_distance(
    lat1,
    lon1,
    lat2,
    lon2
):

    R = 6371.0

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)

    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return R * c


# =========================================================
# 여정 통계
# =========================================================

def get_journey_stats(user_id):

    conn = get_db()

    visits = conn.execute("""
        SELECT
            visits.id,
            visits.visited_at,

            stations.name,
            stations.latitude,
            stations.longitude

        FROM visits

        INNER JOIN stations
            ON visits.station_id = stations.id

        WHERE visits.user_id = ?

        AND stations.latitude IS NOT NULL
        AND stations.longitude IS NOT NULL

        ORDER BY
            visits.visited_at ASC,
            visits.id ASC
    """, (user_id,)).fetchall()

    conn.close()

    total_distance = 0

    journey = []

    previous = None

    for visit in visits:

        current = {
            "name": visit["name"],
            "latitude": visit["latitude"],
            "longitude": visit["longitude"],
            "visited_at": visit["visited_at"]
        }

        if previous:

            total_distance += calculate_distance(
                previous["latitude"],
                previous["longitude"],
                current["latitude"],
                current["longitude"]
            )

        journey.append(current)

        previous = current

    earth_rounds = (
        total_distance / 40075
    )

    return {
        "total_distance": total_distance,
        "earth_rounds": earth_rounds,
        "journey": journey
    }


# =========================================================
# 결산
# =========================================================

def get_report(
    user_id,
    year,
    month=None
):

    conn = get_db()

    # -----------------------------------------------------
    # 기간 계산
    # -----------------------------------------------------

    if month:

        start_date = (
            f"{year:04d}-{month:02d}-01"
        )

        if month == 12:

            end_date = (
                f"{year + 1:04d}-01-01"
            )

        else:

            end_date = (
                f"{year:04d}-{month + 1:02d}-01"
            )

    else:

        start_date = (
            f"{year:04d}-01-01"
        )

        end_date = (
            f"{year + 1:04d}-01-01"
        )

    # -----------------------------------------------------
    # 방문 기록
    # -----------------------------------------------------

    visits = conn.execute("""
        SELECT
            visits.id,
            visits.station_id,
            visits.visited_at,
            visits.emotion,
            visits.photo,

            stations.name,
            stations.latitude,
            stations.longitude

        FROM visits

        INNER JOIN stations
            ON visits.station_id = stations.id

        WHERE visits.user_id = ?

        AND visits.visited_at >= ?
        AND visits.visited_at < ?

        ORDER BY visits.visited_at ASC
    """, (
        user_id,
        start_date,
        end_date
    )).fetchall()

    # -----------------------------------------------------
    # 총 방문 횟수
    # -----------------------------------------------------

    total_visits = len(visits)

    # -----------------------------------------------------
    # 방문한 역
    # -----------------------------------------------------

    visited_station_count = len(
        set(
            visit["station_id"]
            for visit in visits
        )
    )

    # -----------------------------------------------------
    # 사진
    # -----------------------------------------------------

    photo_count = sum(
        1
        for visit in visits
        if visit["photo"]
    )

    # -----------------------------------------------------
    # 감정
    # -----------------------------------------------------

    emotions = {}

    for visit in visits:

        emotion = visit["emotion"]

        if not emotion:
            continue

        emotions[emotion] = (
            emotions.get(emotion, 0) + 1
        )

    most_emotion = None

    if emotions:

        most_emotion = max(
            emotions,
            key=emotions.get
        )

    # -----------------------------------------------------
    # 가장 많이 방문한 역
    # -----------------------------------------------------

    station_counts = {}

    for visit in visits:

        station_id = visit["station_id"]

        if station_id not in station_counts:

            station_counts[station_id] = {
                "name": visit["name"],
                "count": 0
            }

        station_counts[station_id]["count"] += 1

    most_visited_station = None

    if station_counts:

        most_visited_station = max(
            station_counts.values(),
            key=lambda x: x["count"]
        )

    # -----------------------------------------------------
    # 새로 방문한 역
    #
    # "해당 사용자가 과거에 한 번도 방문하지 않은 역"
    # -----------------------------------------------------

    new_station_count = 0

    checked_stations = set()

    for visit in visits:

        station_id = visit["station_id"]

        if station_id in checked_stations:
            continue

        checked_stations.add(station_id)

        previous_visit = conn.execute("""
            SELECT id
            FROM visits
            WHERE user_id = ?
            AND station_id = ?
            AND visited_at < ?
            LIMIT 1
        """, (
            user_id,
            station_id,
            visit["visited_at"]
        )).fetchone()

        if not previous_visit:

            new_station_count += 1

    # -----------------------------------------------------
    # 이동 거리
    # -----------------------------------------------------

    total_distance = 0

    previous = None

    for visit in visits:

        if (
            visit["latitude"] is None
            or visit["longitude"] is None
        ):
            continue

        current = (
            visit["latitude"],
            visit["longitude"]
        )

        if previous:

            total_distance += calculate_distance(
                previous[0],
                previous[1],
                current[0],
                current[1]
            )

        previous = current

    # -----------------------------------------------------
    # 지구 몇 바퀴
    # -----------------------------------------------------

    earth_rounds = (
        total_distance / 40075
    )

    conn.close()

    # -----------------------------------------------------
    # 결과
    # -----------------------------------------------------

    return {
        "year": year,
        "month": month,

        "total_visits":
            total_visits,

        "visited_stations":
            visited_station_count,

        "photo_count":
            photo_count,

        "new_stations":
            new_station_count,

        "most_emotion":
            most_emotion,

        "most_emotion_count":
            (
                emotions.get(
                    most_emotion,
                    0
                )
                if most_emotion
                else 0
            ),

        "most_visited_station":
            most_visited_station,

        "total_distance":
            total_distance,

        "earth_rounds":
            earth_rounds
    }


# =========================================================
# 사용자 생성
# =========================================================

def create_user(
    username,
    password
):

    # -----------------------------------------------------
    # 기본 검증
    # -----------------------------------------------------

    if not username or not username.strip():
        return None

    if not password:
        return None

    username = username.strip()

    # -----------------------------------------------------
    # 비밀번호 해싱
    #
    # 평문 비밀번호는 절대로 DB에 저장하지 않는다.
    # pbkdf2:sha256을 사용하여 안전하게 해싱한다.
    # -----------------------------------------------------

    password_hash = generate_password_hash(
        password,
        method="pbkdf2:sha256",
        salt_length=16
    )

    conn = get_db()

    try:

        cursor = conn.execute("""
            INSERT INTO users (
                username,
                password_hash,
                created_at
            )
            VALUES (?, ?, ?)
        """, (
            username,
            password_hash,
            datetime.now().isoformat()
        ))

        conn.commit()

        user_id = cursor.lastrowid

    except sqlite3.IntegrityError:

        conn.close()

        return None

    conn.close()

    return user_id


# =========================================================
# 사용자 조회
# =========================================================

def get_user_by_username(username):

    conn = get_db()

    user = conn.execute("""
        SELECT *
        FROM users
        WHERE username = ?
    """, (username,)).fetchone()

    conn.close()

    return user


# =========================================================
# 비밀번호 확인
# =========================================================

def check_user_password(
    username,
    password
):

    if not username or not password:
        return None

    user = get_user_by_username(
        username
    )

    if not user:
        return None

    try:

        password_correct = check_password_hash(
            user["password_hash"],
            password
        )

    except (ValueError, TypeError):

        return None

    if not password_correct:
        return None

    return user


