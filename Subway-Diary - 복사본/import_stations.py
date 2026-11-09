import csv

from database import init_db, add_or_update_station


CSV_FILE = "stations.csv"


init_db()

count = 0


with open(
    CSV_FILE,
    "r",
    encoding="cp949"
) as file:

    reader = csv.DictReader(file)

    for row in reader:
        name = row["역명"].strip()
        line = row["호선"].strip()
        station_number = row["고유역번호(외부역코드)"].strip()

        latitude = float(row["위도"])
        longitude = float(row["경도"])

        add_or_update_station(
            name,
            line,
            station_number,
            latitude,
            longitude
        )

        count += 1


print(f"{count}개의 역 데이터를 처리했습니다.")