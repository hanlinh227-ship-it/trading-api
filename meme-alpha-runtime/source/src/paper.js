import fs from "node:fs";

const file =
  "/var/lib/meme-alpha/data/paper/state.json";

const state =
  JSON.parse(
    fs.readFileSync(
      file,
      "utf8"
    )
  );

console.log(
  "=== MEME ALPHA PAPER ==="
);

console.log(
  "MODE=PAPER"
);

console.log(
  `Equity: ${Number(state.equitySol || 0).toFixed(6)} SOL`
);

console.log(
  `Realized PnL: ${Number(state.realizedPnlSol || 0).toFixed(6)} SOL`
);

console.log(
  `Unrealized PnL: ${Number(state.unrealizedPnlSol || 0).toFixed(6)} SOL`
);

console.log(
  `High Water: ${Number(state.highWaterEquitySol || state.equitySol || 0).toFixed(6)} SOL`
);

console.log(
  `Open positions: ${(state.openPositions || []).length}`
);

console.log(
  `Trades: ${(state.trades || []).length}`
);

for (
  const p of
    state.openPositions || []
) {
  console.log(
    `${p.status} | ${p.symbol}` +
    ` | qty=${Number(p.qty).toFixed(4)}` +
    ` | entry=$${Number(p.entryPriceUsd).toPrecision(6)}` +
    ` | MFE=${Number(p.mfePct || 0).toFixed(2)}%` +
    ` | MAE=${Number(p.maePct || 0).toFixed(2)}%`
  );
}

console.log(
  "LIVE_EXECUTION=DISABLED"
);

console.log(
  "PAPER_ENGINE_READY"
);
