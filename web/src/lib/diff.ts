// Tiny Myers-style char-level diff just enough to render side-by-side.
// Returns an array of segments tagged equal/del/ins.

export type DiffSeg = { type: "equal" | "del" | "ins"; text: string };

// LCS-based diff over words (whitespace-preserving) for readability.
export function diffWords(a: string, b: string): DiffSeg[] {
  const aw = tokenize(a);
  const bw = tokenize(b);
  const n = aw.length;
  const m = bw.length;
  // DP table
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = 1; i <= n; i++) {
    for (let j = 1; j <= m; j++) {
      dp[i][j] = aw[i - 1] === bw[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }
  const out: DiffSeg[] = [];
  let i = n;
  let j = m;
  while (i > 0 && j > 0) {
    if (aw[i - 1] === bw[j - 1]) {
      out.push({ type: "equal", text: aw[i - 1] });
      i--;
      j--;
    } else if (dp[i - 1][j] >= dp[i][j - 1]) {
      out.push({ type: "del", text: aw[i - 1] });
      i--;
    } else {
      out.push({ type: "ins", text: bw[j - 1] });
      j--;
    }
  }
  while (i > 0) out.push({ type: "del", text: aw[--i] });
  while (j > 0) out.push({ type: "ins", text: bw[--j] });
  out.reverse();
  return mergeAdjacent(out);
}

function tokenize(s: string): string[] {
  // Keep whitespace so reconstruction preserves layout
  return s.split(/(\s+)/).filter((t) => t.length > 0);
}

function mergeAdjacent(segs: DiffSeg[]): DiffSeg[] {
  const out: DiffSeg[] = [];
  for (const s of segs) {
    const last = out[out.length - 1];
    if (last && last.type === s.type) {
      last.text += s.text;
    } else {
      out.push({ ...s });
    }
  }
  return out;
}
