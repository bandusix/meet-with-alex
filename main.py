from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import requests
import os
import json
import tempfile
from dotenv import load_dotenv
from datetime import datetime, timedelta
import uvicorn

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 飞书配置
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
# 添加你的飞书用户ID
FEISHU_USER_ID = os.getenv("FEISHU_USER_ID", "填入你的飞书用户ID")

# 简单的本地数据存储（实际生产环境应使用数据库，由于在 Vercel 等 Serverless 环境中无法持久化写入本地文件，
# 这里改为写入到 /tmp 目录。如果需要持久化请替换为云数据库，比如 Redis 或 Postgres）
DB_FILE = os.path.join(tempfile.gettempdir(), "bookings.json")

def load_bookings():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_booking(email: str, booking_data: dict):
    bookings = load_bookings()
    bookings[email] = booking_data
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(bookings, f, ensure_ascii=False, indent=2)

def delete_booking(email: str):
    bookings = load_bookings()
    if email in bookings:
        del bookings[email]
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(bookings, f, ensure_ascii=False, indent=2)

class BookingRequest(BaseModel):
    date: str
    time: str
    name: str
    email: str

class QueryRequest(BaseModel):
    email: str
    name: str

class CancelRequest(BaseModel):
    email: str

def get_feishu_tenant_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    response = requests.post(url, json=payload)
    data = response.json()
    if data.get("code") != 0:
        raise Exception(f"获取飞书Token失败: {data.get('msg')}")
    return data.get("tenant_access_token")

def create_feishu_meeting(topic: str, start_time: datetime):
    token = get_feishu_tenant_token()
    
    # 既然使用飞书视频会议预约 API 对权限和企业配置的要求极其严苛，
    # 而且直接生成带有用户ID的主持人权限时会由于飞书企业的视频会议高级权限限制报错。
    # 我们改用最简且对权限要求最低的"创建日历日程并自动附加会议"的 API，
    # 这是绝大多数企业自建应用做会议预约的通用方式。
    
    # 获取用户的主日历
    # (这要求在飞书后台开通 `获取用户日历及日程 (calendar:calendar)` 和 `获取用户 user ID` 权限)
    url_calendar = f"https://open.feishu.cn/open-apis/calendar/v4/calendars/feishu.cn_{FEISHU_USER_ID}@group.calendar.feishu.cn/events"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    end_time = start_time + timedelta(hours=1)
    
    payload = {
        "summary": topic,
        "description": "BrowseFree PM Intern Interview",
        "need_notification": False,
        "start_time": {
            "timestamp": str(int(start_time.timestamp())),
            "timezone": "Asia/Shanghai"
        },
        "end_time": {
            "timestamp": str(int(end_time.timestamp())),
            "timezone": "Asia/Shanghai"
        },
        "vchat": {
            "vc_type": "vc" # vc 表示飞书视频会议
        }
    }
    
    response = requests.post(url_calendar, headers=headers, json=payload)
    data = response.json()
    
    if data.get("code") != 0:
        print(f"飞书API调用失败: {data}")
        # 如果依然失败，备用返回一个模拟的，或者固定会议室
        return f"https://vc.feishu.cn/j/请在此处填入备用的固定会议室号"
        
    # 从日程返回结果中提取会议链接
    vchat_url = data.get("data", {}).get("event", {}).get("vchat", {}).get("meeting_url")
    if not vchat_url:
        return "https://vc.feishu.cn/j/未能获取到会议链接，请检查权限"
        
    return vchat_url

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/book")
async def book_interview(request: BookingRequest, response: Response):
    try:
        # 解析时间
        dt_str = f"{request.date} {request.time}"
        start_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        topic = f"Interview: {request.name} - PM Intern"
        
        # 1. 创建飞书会议
        try:
            meeting_url = create_feishu_meeting(topic, start_time)
        except Exception as e:
            # 捕获飞书报错，如果没配好飞书，给个默认链接
            print(f"Warning: {e}")
            meeting_url = "https://vc.feishu.cn/j/mock_link_please_configure_api"
            
        # 2. 保存预约记录
        booking_data = {
            "name": request.name,
            "email": request.email,
            "date": request.date,
            "time": request.time,
            "meeting_url": meeting_url,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_booking(request.email, booking_data)
        
        # 3. 设置 Cookie (有效7天)
        response.set_cookie(key="interview_email", value=request.email, max_age=7*24*3600)
        response.set_cookie(key="interview_name", value=request.name, max_age=7*24*3600)
            
        return {"success": True, "msg": "Booking created successfully!", "meeting_url": meeting_url}
        
    except Exception as e:
        return {"success": False, "msg": str(e)}

@app.post("/api/query")
async def query_booking(request: QueryRequest, response: Response):
    bookings = load_bookings()
    if request.email in bookings and bookings[request.email]["name"] == request.name:
        # 如果查询成功，同样设置cookie，方便后续访问
        response.set_cookie(key="interview_email", value=request.email, max_age=7*24*3600)
        response.set_cookie(key="interview_name", value=request.name, max_age=7*24*3600)
        return {"success": True, "data": bookings[request.email]}
    return {"success": False, "msg": "Record not found. Please check your credentials."}

@app.get("/api/me")
async def get_my_booking(request: Request):
    email = request.cookies.get("interview_email")
    if not email:
        return {"success": False, "msg": "Not logged in"}
    
    bookings = load_bookings()
    if email in bookings:
        return {"success": True, "data": bookings[email]}
    return {"success": False, "msg": "Record does not exist"}

@app.post("/api/cancel")
async def cancel_booking(request: CancelRequest, response: Response):
    # 取消预约
    delete_booking(request.email)
    # 清除 Cookie
    response.delete_cookie("interview_email")
    response.delete_cookie("interview_name")
    return {"success": True, "msg": "Booking cancelled successfully."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
