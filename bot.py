import os, ccxt, pandas as pd, pandas_ta as ta, asyncio
import mplfinance as mpf
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", "0"))

WATCHLIST = ["DOGE/USDT","SHIB/USDT","PEPE/USDT","WIF/USDT","BONK/USDT","FLOKI/USDT","POPCAT/USDT","BRETT/USDT"]

exchange = ccxt.binance()

def get_df(symbol, tf):
    bars = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=100)
    df = pd.DataFrame(bars, columns=['time','open','high','low','close','vol'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    df.set_index('time', inplace=True)
    df['EMA9'] = ta.ema(df['close'], 9)
    df['EMA21'] = ta.ema(df['close'], 21)
    df['RSI'] = ta.rsi(df['close'], 14)
    df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['VOL_AVG20'] = df['vol'].rolling(20).mean()
    return df

def check_valid_signal(df):
    last = df.iloc[-1]
    if pd.isna(last['EMA9']):
        return None
    gap = abs(last['EMA9'] - last['EMA21']) / last['close'] * 100
    vol_ok = last['vol'] > last['VOL_AVG20']
    rsi = last['RSI']
    if last['EMA9'] > last['EMA21'] and gap >= 0.5 and vol_ok and 50 <= rsi <= 70:
        return "LONG VALID"
    if last['EMA9'] < last['EMA21'] and gap >= 0.5 and vol_ok and 30 <= rsi <= 50:
        return "SHORT VALID"
    return None

def build_text_and_chart(symbol, mode, tf):
    df = get_df(symbol, tf)
    last = df.iloc[-1]
    price = last['close']
    atr = last['ATR']
    gap = abs(last['EMA9']-last['EMA21'])/price*100
    signal = check_valid_signal(df)
    bias = signal if signal else "WAIT - Fake Cross"
    sl = price - 1.5*atr if "LONG" in str(bias) else price + 1.5*atr if "SHORT" in str(bias) else price - 1.5*atr
    tp2 = price + 2*atr if "LONG" in str(bias) else price - 2*atr if "SHORT" in str(bias) else price
    chart_file = f"/tmp/{symbol.replace('/','')}_{mode}.png"
    try:
        mpf.plot(df.tail(60), type='candle', mav=(9,21), volume=True, style='yahoo', savefig=chart_file)
    except:
        chart_file = None
    text = f"📊 *{symbol} | {mode.upper()}*\nHarga ${price:.8f}\nGap {gap:.2f}% RSI {last['RSI']:.1f}\nBias *{bias}*\nSL ${sl:.8f} TP2 ${tp2:.8f}"
    return text, chart_file

async def auto_scanner(context):
    print("Scanning memecoins...")
    for symbol in WATCHLIST:
        for mode, tf in [("SCALPING","15m"),("SWING","1h")]:
            try:
                df = get_df(symbol, tf)
                signal = check_valid_signal(df)
                if signal:
                    last = df.iloc[-1]
                    price = last['close']
                    atr = last['ATR']
                    sl = price - 1.5*atr if "LONG" in signal else price + 1.5*atr
                    tp2 = price + 2*atr if "LONG" in signal else price - 2*atr
                    msg = f"🚨 *MEME {mode}* {symbol} {tf} *{signal}* Harga ${price:.8f} SL ${sl:.8f} TP2 ${tp2:.8f} \n/analisa {symbol.replace('/','')} {mode.lower()}"
                    await context.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
            except Exception as e:
                print(e)
            await asyncio.sleep(1.5)

async def start(update, context):
    await update.message.reply_text("Bot Memecoin EMA 9/21 Aktif! 🚀\n/analisa PEPE scalping\n/analisa DOGE swing\nAuto alert 15m ON.")

async def analisa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Pakai: /analisa PEPE scalping\nList: DOGE SHIB PEPE WIF BONK FLOKI POPCAT BRETT")
        return
    raw = context.args[0].upper()
    mode = context.args[1].lower() if len(context.args)>1 else "scalping"
    symbol = raw if "/" in raw else raw.replace("USDT","/USDT")
    tf = "1h" if mode=="swing" else "15m"
    text, chart = build_text_and_chart(symbol, mode, tf)
    if chart and os.path.exists(chart):
        await update.message.reply_photo(photo=open(chart,'rb'), caption=text, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("analisa", analisa))
app.job_queue.run_repeating(auto_scanner, interval=900, first=20)

print("Bot Memecoin jalan...")
app.run_polling()