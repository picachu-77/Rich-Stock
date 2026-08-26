"use client";

/**
 * 무언가 잘못됐을 때 보여주는 화면.
 * 흰 화면만 뜨면 뭐가 문제인지 알 수 없으므로, 무엇을 확인해야 할지 적어둡니다.
 */
export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="wrap">
      <div className="note" style={{ marginTop: 24 }}>
        <b>화면을 불러오지 못했습니다.</b>
        <br />
        데이터베이스에 연결하지 못했을 수 있습니다. 잠시 뒤 다시 시도해 주세요.
      </div>
      <button
        className="pill"
        style={{ minHeight: 48, width: "100%", justifyContent: "center" }}
        onClick={reset}
      >
        다시 시도
      </button>
    </main>
  );
}
