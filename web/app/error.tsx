"use client";

/**
 * 무언가 잘못됐을 때.
 * 흰 화면만 뜨면 뭐가 문제인지 알 수 없으니, 무엇을 할 수 있는지 적습니다.
 */
export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="wrap">
      <div className="note" style={{ marginTop: 32 }}>
        <b>시세를 불러오지 못했습니다.</b>
        <br />
        데이터베이스에 연결하지 못했습니다. 잠시 뒤 다시 시도해 주세요.
      </div>
      <button className="more" onClick={reset}>다시 시도</button>
    </div>
  );
}
