import os, json, time
import requests
RPC_URL = os.getenv("RPC_URL")

def rpc_call(method, params):
    r = requests.post(
        RPC_URL,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        },
        timeout=20
    )
    r.raise_for_status()
    return r.json()["result"]
TG_TOKEN = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

CHAIN_ID = "solana"
MAX_MC = float(os.getenv("MAX_MC", "15000"))
MIN_LIQ = float(os.getenv("MIN_LIQ", "3000"))
MAX_AGE_MIN = int(os.getenv("MAX_AGE_MIN", "60"))  # only alert recent pools

STATE_FILE = "state.json"
DEX = "https://api.dexscreener.com"

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"seen_pairs": [], "seen_tokens": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

    def tg_send(text):
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(
        url,
        json={
            "chat_id": TG_CHAT_ID,
            "text": text,
            "disable_web_page_preview": True
        },
        timeout=20
    )

    def is_mint_safe(token_address):
         try:
            result = rpc_call("getAccountInfo", [
            token_address,
            {"encoding": "jsonParsed"}
        ])

        if not result or not result.get("value"):
            return False

        info = result["value"]["data"]["parsed"]["info"]

        mint_authority = info.get("mintAuthority")
        freeze_authority = info.get("freezeAuthority")

        if mint_authority is not None:
            return False

        if freeze_authority is not None:
            return False

        return True

     except Exception:
        return False


def is_holder_distribution_safe(token_address, max_percent=30):
    try:
        result = rpc_call("getTokenLargestAccounts", [token_address])

        if not result:
            return False

        accounts = result.get("value", [])
        total_supply_data = rpc_call("getTokenSupply", [token_address])
        total_supply = int(total_supply_data["value"]["amount"])

        for acc in accounts:
            amount = int(acc["amount"])
            percent = (amount / total_supply) * 100

            if percent > max_percent:
                return False

        return True

       except Exception:
        return False
    
    requests.post(url, json={
        "chat_id": TG_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }, timeout=20)

def get_latest_tokens():
    tokens = []

    # latest token profiles + latest boosts
    for endpoint in ("/token-profiles/latest/v1", "/token-boosts/latest/v1"):
        r = requests.get(DEX + endpoint, timeout=20)
        r.raise_for_status()
        data = r.json()
        items = data if isinstance(data, list) else data.get("data", data.get("items", []))
        for it in items:
            if (it.get("chainId") or "").strip().lower() == CHAIN_ID:
                addr = (it.get("tokenAddress") or "").strip()
                if addr:
                    tokens.append(addr)

    # de-dupe
    seen = set()
    out = []
    for a in tokens:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out

def get_token_pools(token_addr):
    url = f"{DEX}/token-pairs/v1/{CHAIN_ID}/{token_addr}"
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else data.get("pairs", [])

def pick_good_pairs(pairs):
    now_ms = int(time.time() * 1000)
    good = []
    for p in pairs:
        liq_usd = (p.get("liquidity") or {}).get("usd")
        mc = p.get("marketCap") or p.get("fdv")
        created = p.get("pairCreatedAt")
        if liq_usd is None or mc is None or created is None:
            continue

        age_min = (now_ms - int(created)) / 60000.0
        if age_min < 0 or age_min > MAX_AGE_MIN:
            continue

        if float(mc) <= MAX_MC and float(liq_usd) >= MIN_LIQ:
            good.append((age_min, p))

    good.sort(key=lambda x: x[0])  # newest first
    return [p for _, p in good]

def fmt_alert(p):
    name = ((p.get("baseToken") or {}).get("symbol") or "UNKNOWN").strip()
    base_addr = ((p.get("baseToken") or {}).get("address") or "").strip()
    url = (p.get("url") or "").strip()

    liq = (p.get("liquidity") or {}).get("usd") or 0
    mc = p.get("marketCap") or p.get("fdv") or 0
    tx5 = ((p.get("txns") or {}).get("m5") or {})
    buys = tx5.get("buys")
    sells = tx5.get("sells")

    lines = []
    lines.append("🚀 NEW EARLY GEM (FILTERED)")
    lines.append(f"Name: ${name}")
    lines.append(f"MC: ${int(mc):,}")
    lines.append(f"Liquidity: ${int(liq):,}")
    if buys is not None and sells is not None:
        lines.append(f"Buys/Sells (5m): {buys}/{sells}")
    lines.append("")
    lines.append("Contract (copy only):")
    lines.append(base_addr)
    if url:
        lines.append("")
        lines.append(f"Chart: {url}")
    return "\n".join(lines)

def main():
    state = load_state()
    seen_pairs = set(state.get("seen_pairs", []))
    seen_tokens = set(state.get("seen_tokens", []))

    tokens = get_latest_tokens()

    for t in tokens:
        if t in seen_tokens:
            continue
        seen_tokens.add(t)

        try:
            pairs = get_token_pools(t)
        except Exception:
            continue

        for p in pick_good_pairs(pairs):
            pair_addr = (p.get("pairAddress") or "").strip()
            if not pair_addr or pair_addr in seen_pairs:
                continue

            seen_pairs.add(pair_addr)
            if not is_mint_safe(t):
    continue

if not is_holder_distribution_safe(t):
    continue
            tg_send(fmt_alert(p))

    state["seen_pairs"] = list(seen_pairs)[-2000:]
    state["seen_tokens"] = list(seen_tokens)[-2000:]
    save_state(state)

if __name__ == "__main__":
    main()
