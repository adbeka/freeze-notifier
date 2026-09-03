import asyncio
import statistics
import sys
import time

import httpx

URL = "http://127.0.0.1:8000/api/status?segment=dept-ro"


async def one_request(client: httpx.AsyncClient) -> tuple[bool, float]:
    start = time.perf_counter()
    try:
        resp = await client.get(URL, timeout=30.0)
        ok = resp.status_code == 200
    except Exception:
        ok = False
    elapsed = time.perf_counter() - start
    return ok, elapsed


async def run_batch(client: httpx.AsyncClient, n: int) -> None:
    t0 = time.perf_counter()
    results = await asyncio.gather(*[one_request(client) for _ in range(n)])
    total = time.perf_counter() - t0

    successes = [r[1] for r in results if r[0]]
    failures = n - len(successes)
    successes_sorted = sorted(successes)

    def pct(p: float) -> float:
        if not successes_sorted:
            return float("nan")
        idx = min(len(successes_sorted) - 1, int(len(successes_sorted) * p))
        return successes_sorted[idx]

    print(f"n={n:5d}  ok={len(successes):5d}/{n:<5d}  wall={total:6.2f}s  "
          f"p50={pct(0.5)*1000:7.0f}ms  p95={pct(0.95)*1000:7.0f}ms  "
          f"max={ (max(successes_sorted)*1000 if successes_sorted else float('nan')):7.0f}ms  "
          f"fail={failures}")


async def main() -> None:
    sizes = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else [50, 200, 500, 1000, 2000]
    max_n = max(sizes)
    # One client reused for the whole sweep, with keep-alive, so batches don't
    # each open thousands of fresh sockets (that pileup exhausts Windows'
    # loopback ephemeral-port range via TIME_WAIT and produces bogus failures
    # unrelated to server capacity).
    limits = httpx.Limits(max_connections=max_n + 50, max_keepalive_connections=max_n + 50)
    async with httpx.AsyncClient(limits=limits) as client:
        for n in sizes:
            await run_batch(client, n)
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
