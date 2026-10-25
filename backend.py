import hashlib
import hmac
import secrets
from urllib.parse import parse_qsl

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import BOT_TOKEN
from database import init_db, ensure_user, get_balance, change_balance, log_play

app = FastAPI()
init_db()

def validate_init_data(init_data: str) -> dict:
    parsed = dict(parse_qsl(init_data))
    hash_str = parsed.pop("hash", "")
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if calc != hash_str:
        raise HTTPException(403, "Invalid initData")
    return parsed

class PlayRequest(BaseModel):
    init_data: str
    bet: int

@app.post("/api/play")
async def play(req: PlayRequest):
    user_data = validate_init_data(req.init_data)
    user_id = int(user_data["id"])
    username = user_data.get("username")
    ensure_user(user_id, username)

    if req.bet <= 0:
        raise HTTPException(400, "Ставка должна быть > 0")
    if get_balance(user_id) < req.bet:
        raise HTTPException(400, "Недостаточно средств")

    change_balance(user_id, -req.bet)

    roll = secrets.randbelow(6) + 1
    win = roll >= 4
    payout = req.bet * 2 if win else 0
    if win:
        change_balance(user_id, payout)

    log_play(user_id, req.bet, str(roll), win, payout)

    return {
        "roll": roll,
        "win": win,
        "payout": payout,
        "new_balance": get_balance(user_id),
    }

app.mount("/webapp", StaticFiles(directory="webapp", html=True), name="webapp")