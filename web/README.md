# 웹 화면 (Next.js · Vercel)

Streamlit 화면을 대신할 새 화면입니다. **한 장씩** 옮기는 중이라,
다 옮길 때까지는 Streamlit 화면도 그대로 두고 씁니다.
둘 다 같은 Supabase 를 보므로 자료는 언제나 같습니다.

## 지금 만들어진 화면

| 주소 | 화면 |
|---|---|
| `/` | 종목 목록 — 찾기(이름·코드·초성) · 정렬 |
| `/stock/[종목코드]` | 종목 상세 — 기간별 수익률 · 시세 차트 · 투자지표 |

## Vercel 설정

### 사람이 화면에서 해야 하는 것 (두 가지뿐)

1. **Settings → Build and Deployment → Root Directory** 를 `web` 으로
   (저장소 맨 위에는 파이썬 수집기가 있어서, 웹 화면은 `web` 폴더에 있습니다)
2. **Settings → Environment Variables** 에 `DATABASE_URL` 추가
   Supabase 의 **Session pooler** 연결 문자열을 넣습니다.

### `vercel.json` 이 대신 해주는 것

`framework: "nextjs"`
  Vercel 은 저장소 맨 위의 `app.py`(Streamlit)를 보고 이 프로젝트를
  **파이썬 프로젝트로 기억해** 버립니다. 그러면 Next.js 를 빌드하지 않고
  파이썬 실행 파일을 찾다가 실패합니다.
      Error: No python entrypoint found.
  화면 설정에서도 바꿀 수 있지만, 여기 적어두면 코드와 함께 남아서
  다시 연결하거나 설정이 초기화돼도 같은 문제가 반복되지 않습니다.

`git.deploymentEnabled`
  작업용 가지까지 배포하면 푸시 한 번에 빌드가 두 번 돕니다. `main` 만 켭니다.

> ⚠️ 이 파일에는 **주석을 쓸 수 없습니다.** Vercel 이 정해진 항목만 받기
> 때문에 `//` 같은 키를 넣으면 빌드가 통째로 실패합니다.
>     The `vercel.json` schema validation failed: should NOT have additional property `//`
> 설명이 필요하면 이 문서에 적어주세요.

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
