# 웹 화면 (Next.js · Vercel)

Streamlit 화면을 대신할 새 화면입니다. **한 장씩** 옮기는 중이라,
다 옮길 때까지는 Streamlit 화면도 그대로 두고 씁니다.
둘 다 같은 Supabase 를 보므로 자료는 언제나 같습니다.

## 지금 만들어진 화면

| 주소 | 화면 |
|---|---|
| `/` | 종목 목록 — 찾기(이름·코드·초성) · 정렬 |
| `/stock/[종목코드]` | 종목 상세 — 기간별 수익률 · 시세 차트 · 투자지표 |

## Vercel 설정 (한 번만)

1. **Settings → General → Root Directory** 를 `web` 으로
   (저장소 맨 위에는 파이썬 수집기가 있어서, 웹 화면은 `web` 폴더에 있습니다)
2. **Settings → Environment Variables** 에 `DATABASE_URL` 추가
   Supabase 의 **Session pooler** 연결 문자열을 넣습니다.

## 왜 이렇게 만들었나

**빠르기** — 시세는 하루에 한 번만 바뀝니다. 그래서 화면을 미리 만들어
두고(`revalidate = 3600`) CDN 에서 바로 내려줍니다. 볼 때마다 데이터베이스에
물어보던 Streamlit 과 다릅니다.

**가벼움** — 차트 라이브러리를 쓰지 않고 SVG 로 직접 그립니다.
라이브러리 하나가 수백 KB 라 휴대폰에서 화면이 늦게 뜨기 때문입니다.
지금 첫 화면이 받는 자바스크립트는 모두 합쳐 107KB 입니다.

**찾기가 즉각적** — 전 종목을 한 번 받아두고 브라우저에서 거릅니다.
글자를 칠 때마다 서버에 다녀오지 않아 기다림이 없습니다.

**손가락 크기** — 누르는 것은 모두 48px 이상입니다.
(손끝이 닿는 넓이가 대략 45px 입니다)

## 계산은 파이썬 쪽과 같아야 합니다

`lib/periods.ts` 의 `NEAR_DAYS` 는 `src/market_data.py` 의 `NEAR_DAYS` 와
**같은 값이어야 합니다.** 두 화면이 다른 수익률을 보여주면 어느 쪽을
믿어야 할지 알 수 없습니다.

## 내 컴퓨터에서 돌려보기

```bash
cd web
npm install
DATABASE_URL="postgresql://..." npm run dev
```
