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
from pypinyin import lazy_pinyin

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

class DateQueryRequest(BaseModel):
    date: str

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
    
    # 既然之前报错，那我们退一步，用 json 参数，并且不要在任何地方发送可能导致问题的中文字符
    
    url_calendar = f"https://open.feishu.cn/open-apis/calendar/v4/calendars/feishu.cn_{FEISHU_USER_ID}@group.calendar.feishu.cn/events"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url_calendar, headers=headers, json=payload)
        response.encoding = 'utf-8'
        data = response.json()
    except Exception as e:
        print("Encode error fallback triggered:", e)
        # 如果依然报错（比如底层 httplib 报 latin-1 错误），说明是 Python requests 的一个已知 bug，
        # 我们退回使用纯 ASCII
        payload["summary"] = "Interview: Candidate - PM Intern"
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

def check_feishu_freebusy(target_date: str) -> list:
    """
    检查指定日期飞书用户的忙闲状态，返回被占用的时间段列表
    返回格式例如: ["18:00", "19:30"]
    """
    try:
        token = get_feishu_tenant_token()
        
        # 飞书忙闲接口
        url = "https://open.feishu.cn/open-apis/calendar/v4/freebusy/list?user_id_type=open_id"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # 构造当天的查询时间范围 (从当天的 00:00 到 23:59)
        start_dt = datetime.strptime(f"{target_date} 00:00:00", "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(f"{target_date} 23:59:59", "%Y-%m-%d %H:%M:%S")
        
        payload = {
            "time_min": f"{start_dt.isoformat()}+08:00",
            "time_max": f"{end_dt.isoformat()}+08:00",
            "user_id": FEISHU_USER_ID
        }
        
        # 直接使用 json 参数
        response = requests.post(url, headers=headers, json=payload)
        response.encoding = 'utf-8'
        data = response.json()
        
        occupied_slots = []
        
        if data.get("code") == 0:
            freebusy_list = data.get("data", {}).get("freebusy_list", [])
            for item in freebusy_list:
                # 提取开始时间和结束时间
                start_str = item.get("start_time")
                end_str = item.get("end_time")
                if not start_str or not end_str:
                    continue
                    
                # 飞书返回的时间格式如: 2024-03-22T18:00:00+08:00
                start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                
                # 将占用的时间段转化为我们的 slot 格式 (HH:MM)
                # 面试时间固定在晚上 18:00 - 21:00，每次半小时
                # 如果会议和我们的 Slot 有任何交集，就认为该 Slot 被占用
                available_slots = ["18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00"]
                for slot in available_slots:
                    slot_start = datetime.strptime(f"{target_date} {slot}:00+0800", "%Y-%m-%d %H:%M:%S%z")
                    slot_end = slot_start + timedelta(hours=1) # 假设面试需要1小时
                    
                    # 判断时间段是否重叠 (A_start < B_end and A_end > B_start)
                    if start_time < slot_end and end_time > slot_start:
                        if slot not in occupied_slots:
                            occupied_slots.append(slot)
                            
        return occupied_slots
    except Exception as e:
        print(f"查询飞书忙闲状态失败: {e}")
        return [] # 如果查询失败，默认全部可用，保证流程不中断

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/api/slots")
async def get_available_slots(request: DateQueryRequest):
    try:
        # 获取飞书日历真实占用情况
        occupied_slots = check_feishu_freebusy(request.date)
        
        # 获取我们系统里已经预约的本地记录（双重保险）
        bookings = load_bookings()
        local_occupied = []
        for b in bookings.values():
            if b.get("date") == request.date:
                local_occupied.append(b.get("time"))
                # 如果面试按1小时算，比如约了18:00，那18:30也不能约了
                time_obj = datetime.strptime(b.get("time"), "%H:%M")
                next_half_hour = (time_obj + timedelta(minutes=30)).strftime("%H:%M")
                prev_half_hour = (time_obj - timedelta(minutes=30)).strftime("%H:%M")
                local_occupied.append(next_half_hour)
                local_occupied.append(prev_half_hour)
                
        # 合并所有被占用的时间段
        all_occupied = list(set(occupied_slots + local_occupied))
        
        # 所有的候选时间
        all_slots = ["18:00", "18:30", "19:00", "19:30", "20:00", "20:30", "21:00"]
        
        # 过滤出真正可用的时间
        available_slots = [slot for slot in all_slots if slot not in all_occupied]
        
        return {"success": True, "data": available_slots, "occupied": all_occupied}
    except Exception as e:
        return {"success": False, "msg": str(e)}

@app.post("/api/book")
async def book_interview(request: BookingRequest, response: Response):
    try:
        # 解析时间
        dt_str = f"{request.date} {request.time}"
        start_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        
        # 将中文名字转换为拼音，确保飞书 API 在接受时绝对不会因为字符编码报错
        # lazy_pinyin("成都车") -> ['cheng', 'dou', 'che']
        # 然后用空格拼起来，并使用 title() 让首字母大写 -> "Cheng Dou Che"
        pinyin_list = lazy_pinyin(request.name)
        pinyin_name = " ".join(pinyin_list).title()
        
        topic = f"Interview: {pinyin_name} - PM Intern"
        
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
        # 注意：cookie的value如果包含非ascii字符（如中文姓名），必须进行URL编码
        # 否则在 set_cookie 内部底层组装 HTTP Headers 时会触发 latin-1 编码错误
        import urllib.parse
        encoded_name = urllib.parse.quote(request.name)
        
        response.set_cookie(key="interview_email", value=request.email, max_age=7*24*3600)
        response.set_cookie(key="interview_name", value=encoded_name, max_age=7*24*3600)
            
        return {"success": True, "msg": "Booking created successfully!", "meeting_url": meeting_url}
        
    except Exception as e:
        return {"success": False, "msg": str(e)}

@app.post("/api/query")
async def query_booking(request: QueryRequest, response: Response):
    bookings = load_bookings()
    if request.email in bookings and bookings[request.email]["name"] == request.name:
        # 如果查询成功，同样设置cookie，方便后续访问
        import urllib.parse
        encoded_name = urllib.parse.quote(request.name)
        
        response.set_cookie(key="interview_email", value=request.email, max_age=7*24*3600)
        response.set_cookie(key="interview_name", value=encoded_name, max_age=7*24*3600)
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
