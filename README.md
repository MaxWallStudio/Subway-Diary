# Station Diary PWA

GitHub Pages용 정적 PWA입니다. 계정이나 서버 없이 사용할 수 있고 방문 표시와 메모는 사용 중인 브라우저의 로컬 저장소에 보관됩니다. 기기 간 동기화는 없으므로 **기록 백업**으로 JSON 파일을 저장하고 다른 브라우저에서 **백업 불러오기**를 사용하세요.

## GitHub Pages 배포

1. 저장소의 **Settings → Pages**로 이동합니다.
2. **Deploy from a branch**를 고르고 기본 브랜치의 **/docs** 폴더를 선택합니다.
3. 저장하면 표시되는 Pages 주소로 접속합니다. HTTPS에서 설치와 오프라인 캐시가 동작합니다.

현재 배포용 사이트는 `docs/` 안에 있습니다. 역 데이터 원본은 `stations.csv`입니다.
