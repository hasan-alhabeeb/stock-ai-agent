import google.genai as genai
import yfinance as yf
import pandas as pd
import gradio as gr
import plotly.graph_objects as go
from datetime import datetime
import os

# إعداد API ومكافحة السجلات
API_KEY = "AQ.Ab8RN6Kixkxp3_kW4g_a9TgAa975oRW4LrVlFu69DNj9f1kAKA"
client = genai.Client(api_key=API_KEY)
LOG_FILE = "agent_recommendations_log.csv"

if not os.path.exists(LOG_FILE):
    df_empty = pd.DataFrame(columns=["Timestamp", "Ticker", "Current_Price", "Decision", "Status"])
    df_empty.to_csv(LOG_FILE, index=False)

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_stock_full(ticker_symbol):
    if not ticker_symbol:
        return "الرجاء إدخال رمز السهم أولاً.", None, None
    
    ticker_symbol = ticker_symbol.upper().strip()
    stock = yf.Ticker(ticker_symbol)
    hist = stock.history(period="6mo")
    info = stock.info
    
    if hist.empty:
        return f"عذراً، لم يتم العثور على بيانات للسهم {ticker_symbol}.", None, None
        
    current_price = hist['Close'].iloc[-1]
    hist['SMA_50'] = hist['Close'].rolling(window=50).mean()
    hist['RSI'] = calculate_rsi(hist['Close'])
    
    sma_50 = hist['SMA_50'].iloc[-1]
    rsi = hist['RSI'].iloc[-1]
    
    pe_ratio = info.get('trailingPE', 'غير متوفر')
    eps = info.get('trailingEps', 'غير متوفر')
    market_cap = info.get('marketCap', 'غير متوفر')
    if isinstance(market_cap, (int, float)):
        market_cap = f"${market_cap / 1e9:.2f} مليار"

    news_list = stock.news
    headlines = []
    if news_list:
        for item in news_list[:5]:
            title = item.get('title') or item.get('content', {}).get('title', '')
            if title:
                headlines.append(f"- {title}")
    news_text = "\n".join(headlines) if headlines else "لا توجد أخبار حديثة متاحة حالياً."

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=hist.index, open=hist['Open'], high=hist['High'],
        low=hist['Low'], close=hist['Close'], name='سعر السهم'
    ))
    fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_50'], mode='lines', name='SMA 50'))
    fig.update_layout(
        title=f"الرسم البياني التفاعلي لسهم {ticker_symbol}",
        xaxis_title="التاريخ", yaxis_title="السعر ($)",
        template="plotly_white", margin=dict(l=20, r=20, t=40, b=20)
    )

    stop_loss = current_price * 0.95
    take_profit = current_price * 1.10
    
    prompt = f"""
    أنت وكيل ذكاء اصطناعي خبير في التحليل المالي والأساسي والفني (FMVA).
    بيانات سهم {ticker_symbol}:
    - السعر الحالي: ${current_price:.2f}
    - مكرر الربحية (P/E Ratio): {pe_ratio}
    - ربحية السهم (EPS): {eps}
    - القيمة السوقية: {market_cap}
    - المتوسط المتحرك 50 يوم: ${sma_50:.2f}
    - مؤشر القوة النسبية RSI: {rsi:.2f}
    - وقف الخسارة المقترح: ${stop_loss:.2f}
    - هدف الربح المقترح: ${take_profit:.2f}
    
    أحدث الأخبار:
    {news_text}
    
    المطلوب:
    1. تقييم التحليل الأساسي والمالي للشركة.
    2. تقييم التحليل الفني ومشاعر الأخبار.
    3. تحديد مستويات المخاطر وتوصية نهائية صريحة (شراء / بيع / احتفاظ).
    """
    
    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt,
    )
    return response.text, current_price, fig

def confirm_decision(user_choice, ticker_symbol, current_price):
    if not ticker_symbol or not current_price:
        return "الرجاء أدخل رمز السهم والتحليل أولاً.", pd.read_csv(LOG_FILE), LOG_FILE
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "Approved" if user_choice == "نعم" else "Rejected"
    
    new_log = pd.DataFrame([{
        "Timestamp": now,
        "Ticker": ticker_symbol.upper(),
        "Current_Price": f"${current_price:.2f}",
        "Decision": user_choice,
        "Status": status
    }])
    new_log.to_csv(LOG_FILE, mode='a', header=False, index=False)
    
    updated_df = pd.read_csv(LOG_FILE)
    msg = f"✓ تم اعتُماد التوصية وحفظها لسهم {ticker_symbol}!" if user_choice == "نعم" else f"✗ تم رفض التوصية لسهم {ticker_symbol}."
    return msg, updated_df, LOG_FILE

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🤖 المنظومة المالية الفائقة (Financial AI Professional Agent)")
    gr.Markdown("تحليل أساسي + تحليل فني + رسم بياني تفاعلي + أخبار + إدارة مخاطر + تصدير السجلات.")
    
    price_state = gr.State()
    
    with gr.Row():
        ticker_input = gr.Textbox(label="رمز السهم (Ticker)", placeholder="مثال: AAPL, NVDA, TSLA")
        analyze_btn = gr.Button("بدء التحليل الفائق 🚀", variant="primary")
    
    with gr.Row():
        output_analysis = gr.Textbox(label="تقرير الذكاء الاصطناعي الشامل", lines=15, scale=1)
        stock_chart = gr.Plot(label="الرسم البياني التفاعلي للسهم", scale=1)
    
    gr.Markdown("---")
    gr.Markdown("### 🛡️ نظام الحماية البشري وتصدير السجلات")
    
    with gr.Row():
        confirm_btn = gr.Button("أوافق على التوصية (نعم)", variant="success")
        reject_btn = gr.Button("أرفض التوصية (لا)", variant="stop")
        
    final_status = gr.Textbox(label="حالة القرار", lines=2)
    
    gr.Markdown("### 📜 سجل التوصيات وزر التحميل إلى جهازك")
    log_table = gr.DataFrame(value=pd.read_csv(LOG_FILE), label="سجل التوصيات المحفوظة")
    file_download = gr.File(label="تنزيل ملف السجلات CSV إلى جهازك", value=LOG_FILE)
    
    analyze_btn.click(fn=analyze_stock_full, inputs=ticker_input, outputs=[output_analysis, price_state, stock_chart])
    confirm_btn.click(fn=lambda t, p: confirm_decision("نعم", t, p), inputs=[ticker_input, price_state], outputs=[final_status, log_table, file_download])
    reject_btn.click(fn=lambda t, p: confirm_decision("لا", t, p), inputs=[ticker_input, price_state], outputs=[final_status, log_table, file_download])

demo.launch()
