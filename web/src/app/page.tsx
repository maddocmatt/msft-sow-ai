import Link from "next/link";

export default function Home() {
  return (
    <main
      style={{
        padding: "2rem",
        maxWidth: 720,
        margin: "0 auto",
        fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif",
      }}
    >
      <h1>msft-sow-ai</h1>
      <p>
        Federal SOW + Budgetary Estimate + WBS drafter, with a deterministic SQA
        gatekeeper.
      </p>
      <ul>
        <li>
          <Link href="/score/">Score an artifact bundle</Link>
        </li>
      </ul>
    </main>
  );
}
