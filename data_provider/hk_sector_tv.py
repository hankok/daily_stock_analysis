"""HK sector rankings via TradingView, read through an existing Chrome CDP session.

Non-invasive by design: creates its OWN throwaway target via Target.createTarget
(background=True so it never steals focus) and closes ONLY that target in finally.
It never navigates, focuses, or closes any other tab (e.g. the daily Mancini
level-upsert chart) or the browser itself.

Fully defensive: ANY failure — Chrome/CDP not running, WS rejected, render timeout,
missing column, parse error — returns ([], []) so the market review degrades
gracefully to "暂无板块数据" instead of raising.
"""
import json
import logging
import os
import time

logger = logging.getLogger(__name__)

CDP_URL = os.getenv("TV_CDP_URL", "http://127.0.0.1:9222")
TV_HK_SECTORS_URL = "https://cn.tradingview.com/markets/stocks-hong-kong/sectorandindustry-sector/"
_OVERALL_TIMEOUT = float(os.getenv("TV_CDP_TIMEOUT", "45"))

# Header-aware: find the "涨跌 %" column (NOT 股息收益率%), read that column per row.
_EXTRACT_JS = r"""(()=>{
  const hs=[...document.querySelectorAll('th')].map(x=>x.innerText.trim());
  let ci=hs.findIndex(h=>/^涨跌\s*%/.test(h));
  if(ci<0)return JSON.stringify({err:'no_change_col',hs:hs.slice(0,8)});
  const rows=[...document.querySelectorAll('tbody tr, table tr')];
  const seen=new Set(), out=[];
  for(const r of rows){
    const c=[...r.querySelectorAll('td')].map(x=>x.innerText.trim());
    if(c.length<=ci)continue;
    const name=c[0], chg=c[ci];
    if(!name||seen.has(name))continue;
    if(!/[+\-−]?\d/.test(chg))continue;
    seen.add(name); out.push([name,chg]);
  }
  return JSON.stringify({rows:out});
})()"""


def _parse_pct(s):
    if not s:
        return None
    s = s.replace("−", "-").replace("%", "").replace("+", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def get_hk_sector_rankings(n: int = 5, timeout: float = None):
    """Return (top_sectors, bottom_sectors) as [{'name','change_pct'}], or ([],[]) on any failure."""
    deadline = time.time() + (timeout or _OVERALL_TIMEOUT)
    ws = None
    target = None
    try:
        import requests
        from websocket import create_connection

        ver = requests.get(CDP_URL + "/json/version", timeout=6).json()
        ws = create_connection(ver["webSocketDebuggerUrl"], timeout=15, suppress_origin=True)
        counter = [0]

        def send(method, params=None, session=None):
            counter[0] += 1
            msg = {"id": counter[0], "method": method, "params": params or {}}
            if session:
                msg["sessionId"] = session
            ws.send(json.dumps(msg))
            return counter[0]

        def wait(mid, to=15):
            end = time.time() + to
            while time.time() < end and time.time() < deadline:
                x = json.loads(ws.recv())
                if x.get("id") == mid:
                    return x
            raise TimeoutError(f"cdp wait timeout id={mid}")

        # Own throwaway target, in the background (does not steal focus from other tabs).
        target = wait(send("Target.createTarget", {"url": "about:blank", "background": True}))["result"]["targetId"]
        sess = wait(send("Target.attachToTarget", {"targetId": target, "flatten": True}))["result"]["sessionId"]
        send("Runtime.enable", session=sess)
        send("Page.navigate", {"url": TV_HK_SECTORS_URL}, session=sess)

        rows = []
        while time.time() < deadline:
            time.sleep(3)
            try:
                r = wait(send("Runtime.evaluate",
                              {"expression": _EXTRACT_JS, "returnByValue": True, "awaitPromise": True},
                              session=sess), to=15)
                val = (r.get("result", {}).get("result", {}) or {}).get("value")
                data = json.loads(val) if val else {}
                rows = data.get("rows") or []
                if len(rows) >= 5:
                    break
            except Exception:
                continue

        parsed = []
        for item in rows:
            try:
                name, chg = item[0], item[1]
            except (IndexError, TypeError):
                continue
            pct = _parse_pct(chg)
            if name and pct is not None:
                parsed.append({"name": name, "change_pct": pct})

        if not parsed:
            logger.warning("[HK sectors] TradingView returned no usable rows — skipping HK sector data")
            return [], []

        parsed.sort(key=lambda x: x["change_pct"], reverse=True)
        top = parsed[:n]
        bottom = list(reversed(parsed[-n:]))
        logger.info("[HK sectors] TradingView ok: %d sectors, top=%s", len(parsed), [p["name"] for p in top])
        return top, bottom

    except Exception as e:
        logger.warning("[HK sectors] TradingView CDP unavailable (%s: %s) — skipping HK sector data",
                       type(e).__name__, str(e)[:80])
        return [], []
    finally:
        # Close ONLY our own target; never touch other tabs or the browser.
        try:
            if ws is not None and target is not None:
                ws.send(json.dumps({"id": 999999, "method": "Target.closeTarget", "params": {"targetId": target}}))
        except Exception:
            pass
        try:
            if ws is not None:
                ws.close()
        except Exception:
            pass
