# 📈 Rich Stock — 국내주식 자동 수집 · 조회 시스템

코스피 · 코스닥 전 종목(일반주식 + ETF)의 일별 시세를 매일 자동으로 모아서,
웹 화면으로 조회하는 개인용 시스템입니다.

```
한국거래소  →  [수집기(파이썬)]  →  Neon 데이터베이스  →  [화면(Streamlit)]
                     ↑
              매일 밤 11시 GitHub Actions 가 자동 실행
```

---

## 1. 처음 한 번만 하는 준비

### 1-1. 계정 2개 준비하기

| 무엇 | 어디서 | 비고 |
|---|---|---|
| **Neon** 계정 | https://neon.tech | 데이터 저장 창고. 무료 |
| **한국거래소** 계정 | https://data.krx.co.kr | 시세 조회에 필요. 무료 |

> ⚠️ 한국거래소는 2025년부터 시세 데이터 조회에 **회원 로그인**을 요구합니다.
> 로그인 없이 요청하면 서버가 거부합니다. 우회 방법은 없으니 무료 가입이 필요합니다.

### 1-2. 비밀 정보 넣기

프로젝트 폴더에서 명령창(PowerShell)을 열고:

```powershell
copy .env.example .env
notepad .env
```

메모장이 열리면 세 곳을 본인 값으로 바꾸고 저장합니다.

```
DATABASE_URL=postgresql://...          ← Neon 대시보드에서 복사
KRX_ID=내아이디                          ← data.krx.co.kr 아이디
KRX_PW=내비밀번호                        ← data.krx.co.kr 비밀번호
```

> `.env` 파일은 `.gitignore` 에 등록되어 있어 **깃허브에 절대 올라가지 않습니다.**

### 1-3. 부품 설치

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 1-4. 설정이 잘 됐는지 점검

```powershell
.venv\Scripts\python.exe -m src.check
```

네 항목이 모두 `정상` 으로 나와야 다음으로 넘어갈 수 있습니다.

---

## 2. 데이터 채우기

### 2-1. 표(테이블) 만들기 — 1회

```powershell
.venv\Scripts\python.exe -m src.create_tables
```

### 2-2. 과거 3년치 채우기 — 1회 (오래 걸림)

```powershell
.venv\Scripts\python.exe -m src.backfill
```

- 대략 1~3시간 걸립니다. 진행률과 남은 시간이 화면에 표시됩니다.
- **중간에 멈춰도 됩니다.** 다시 실행하면 받다 만 지점부터 이어서 받습니다.
- 짧게 시험해 보려면: `.venv\Scripts\python.exe -m src.backfill --years 1`

### 2-3. 오늘치만 수집 (수동 실행)

```powershell
.venv\Scripts\python.exe -m src.daily_collect
```

---

## 3. 화면 보기

```powershell
.venv\Scripts\streamlit.exe run app.py
```

웹브라우저가 자동으로 열립니다. 끄려면 명령창에서 `Ctrl+C`.

**기능**
- 전 종목 표 + 종목명/코드 검색
- 시장(코스피/코스닥) · 종류(주식/ETF) 필터
- 시가총액순 · 등락률순 · 기간별 수익률순 정렬
- 종목 클릭 → 시세 추이 차트 + 기간별 수익률(1개월/3개월/6개월/1년/3년)

> 수익률은 외부에서 받아오는 값이 아니라, **데이터베이스에 쌓인 과거 종가로
> 직접 계산**합니다. `(최근 종가 ÷ N개월 전 종가 − 1) × 100`

---

## 4. 매일 자동 실행 (GitHub Actions)

`.github/workflows/daily.yml` 이 매일 **한국시간 밤 11시**에 `src.daily_collect` 를
자동 실행합니다. 내 컴퓨터가 꺼져 있어도 동작합니다.

### 비밀값(Secrets) 등록 — 깃허브 웹사이트에서 1회

1. 깃허브에서 이 저장소 페이지로 이동
2. 상단 **Settings** 탭 클릭
3. 왼쪽 메뉴에서 **Secrets and variables** → **Actions** 클릭
4. 초록색 **New repository secret** 버튼 클릭
5. 아래 3개를 하나씩 등록 (이름은 대소문자까지 정확히)

| Name | Secret |
|---|---|
| `DATABASE_URL` | Neon 연결 문자열 |
| `KRX_ID` | 한국거래소 아이디 |
| `KRX_PW` | 한국거래소 비밀번호 |

### 잘 도는지 확인하기

**Actions** 탭 → 왼쪽에서 **매일 시세 수집** 선택 → 우측 **Run workflow** 버튼으로
지금 바로 시험 실행할 수 있습니다.

---

## 5. 파일 설명

| 파일 | 역할 |
|---|---|
| `.env` | 비밀 정보 (깃허브에 안 올라감) |
| `.env.example` | `.env` 작성 견본 |
| `requirements.txt` | 필요한 부품 목록 |
| `app.py` | 웹 화면 |
| `src/config.py` | 비밀값 읽기 |
| `src/db.py` | 데이터베이스 접속 |
| `src/create_tables.py` | 표 만들기 (1회) |
| `src/krx.py` | 거래소에서 데이터 받기 (로그인 · 재시도 · 분할요청) |
| `src/store.py` | 받은 데이터 저장 (중복 방지) |
| `src/update_tickers.py` | 종목 목록 갱신 |
| `src/backfill.py` | 과거 3년치 채우기 (1회, 이어받기 지원) |
| `src/daily_collect.py` | 매일 수집 |
| `src/check.py` | 설정 점검 도구 |
| `.github/workflows/daily.yml` | 매일 자동 실행 설정 |

---

## 6. 데이터베이스 구조

**ticker** — 종목 목록

| 칸 | 설명 |
|---|---|
| `code` | 종목코드 (기본키) |
| `name` | 종목명 |
| `market` | KOSPI / KOSDAQ |
| `kind` | STOCK / ETF |
| `is_active` | 상장중 여부 (상장폐지 시 FALSE) |
| `first_seen` / `last_seen` | 최초/최종 확인일 |

**daily_price** — 일별 시세

| 칸 | 설명 |
|---|---|
| `code` + `trade_date` | **기본키 (중복 저장 불가)** |
| `close` | 종가 |
| `change_pct` | 등락률 (%) |
| `volume` | 거래량 |
| `market_cap` | 시가총액 |

**ingest_log** — 수집 진행 기록 (이어받기용)

---

## 7. 화면을 인터넷에 올리기 (Streamlit Community Cloud · 무료)

내 컴퓨터가 꺼져 있어도 휴대폰으로 볼 수 있게 됩니다.

### 준비물
GitHub 계정만 있으면 됩니다. 코드는 이미 올라가 있어야 합니다.

### 순서

1. https://share.streamlit.io 접속 → **Continue with GitHub** 으로 로그인
2. **Create app** → **Deploy a public app from GitHub** 선택
3. 아래처럼 채웁니다

   | 칸 | 값 |
   |---|---|
   | Repository | `picachu-77/Rich-Stock` |
   | Branch | `main` |
   | Main file path | `app.py` |

4. **Advanced settings** 를 펼치고 **Secrets** 칸에 아래 한 줄을 넣습니다.
   (`.env` 의 DATABASE_URL 값을 **따옴표로 감싸서** 붙여넣으세요)

   ```toml
   DATABASE_URL = "postgresql://...여기에 Neon 연결 문자열..."
   ```

   > `.env` 와 달리 여기서는 **따옴표가 필요합니다.** 형식이 다릅니다(TOML).
   > 거래소 아이디·비밀번호는 넣지 마세요. 화면은 거래소에 접속하지 않습니다.

5. **Deploy** 클릭 → 3~5분 기다리면 주소가 나옵니다

### ⚠️ 공개 범위 주의

Streamlit Community Cloud 의 앱은 **기본이 전체 공개**입니다.
주소를 아는 사람은 누구나 볼 수 있습니다.

나만 보려면 배포 후:
**앱 화면 우측 하단 Manage app → Settings → Sharing** 에서
공개 범위를 제한하고, 볼 사람의 이메일을 직접 등록하세요.

### 알아둘 점
- 무료 플랜은 **아무도 안 보면 앱이 잠듭니다.** 다시 열면 30초쯤 뒤 깨어납니다.
- 코드를 깃허브에 새로 올리면 앱이 자동으로 갱신됩니다.

---

## 8. 알아두실 점

**ETF 는 시가총액이 빈칸입니다.**
한국거래소가 ETF 스냅샷으로 주는 항목은 `NAV, 시가, 고가, 저가, 종가, 거래량,
거래대금, 기초지수` 뿐이고 시가총액이 없습니다. ETF 규모는 거래대금으로 보세요.

**ETF 등락률은 직접 계산합니다.**
거래소가 ETF 등락률을 주지 않아서, 바로 전 거래일 종가와 비교해 계산합니다.
단, 앞뒤 날짜가 7일 넘게 벌어져 있으면(데이터가 아직 안 채워진 구간 등)
엉뚱한 값이 들어가지 않도록 비워 둡니다.

**화면의 영어 메뉴는 한글로 바꿔치기한 것입니다.**
Streamlit 이 표 머리글 메뉴("Sort ascending" 등)를 영어로 그리는데 이를 한글로
바꾸는 공식 설정이 없습니다. `src/ui_korean.py` 가 화면에 뜬 뒤 글자를 바꿉니다.
Streamlit 이 업데이트되어 일부가 다시 영어로 보이면, 그 파일의 사전에 한 줄
추가하면 됩니다.

---

## 9. 문제가 생겼을 때

가장 먼저:

```powershell
.venv\Scripts\python.exe -m src.check
```

| 증상 | 원인과 해결 |
|---|---|
| `KRX 로그인 실패` | `.env` 의 KRX_ID/KRX_PW 확인. data.krx.co.kr 에 브라우저로 직접 로그인해 보세요 (비밀번호 변경 요구 화면이 떠 있으면 먼저 변경) |
| `DATABASE_URL 을 찾지 못했습니다` | `.env` 가 없거나 값이 비어 있음. `copy .env.example .env` 후 값 입력 |
| 접속은 되는데 데이터가 0건 | `src.backfill` 을 아직 안 돌렸거나 도중에 멈춤. 다시 실행하면 이어서 받습니다 |
| Neon 접속이 가끔 느림 | 무료 플랜은 안 쓰면 잠듭니다. 첫 요청 시 몇 초 걸린 뒤 깨어납니다 |
