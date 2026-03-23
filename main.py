from fastapi import FastAPI, HTTPException, Request, Response, Form, UploadFile, File
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

def upload_resume_to_feishu(file_content: bytes, filename: str) -> str:
    """
    将文件上传到飞书，并返回 file_token。
    根据飞书文档，日历附件只能通过 /drive/v1/files/upload_all 接口上传。
    由于这是一个简单的 Serverless 部署，我们使用直接上传。
    """
    try:
        token = get_feishu_tenant_token()
        url = "https://open.feishu.cn/open-apis/drive/v1/files/upload_all"
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        # parent_node 需要是应用文件夹，如果不指定或者指定错误，可以留空或者使用特定的 folder_token
        # 为了兼容性，使用 "" 代表根目录，或者在企业设置中创建一个特定的文件夹
        # 此处使用 requests 的 files 参数来上传 multipart/form-data
        files = {
            'file': (filename, file_content, 'application/pdf')
        }
        data = {
            'file_name': filename,
            'parent_type': 'explorer',
            'parent_node': ''
        }
        
        response = requests.post(url, headers=headers, files=files, data=data)
        res_data = response.json()
        
        if res_data.get("code") == 0:
            return res_data.get("data", {}).get("file_token")
        else:
            print(f"Resume upload failed: {res_data}")
            return None
    except Exception as e:
        print(f"Exception during resume upload: {e}")
        return None

def bind_resume_to_event(calendar_id: str, event_id: str, file_token: str):
    """将上传成功的飞书云文档绑定到具体的日历事件附件中"""
    if not file_token:
        return
        
    try:
        token = get_feishu_tenant_token()
        url = f"https://open.feishu.cn/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # 飞书 PATCH 接口增量更新
        payload = {
            "attachments": [
                {
                    "file_token": file_token
                }
            ]
        }
        
        response = requests.patch(url, headers=headers, json=payload)
        if response.json().get("code") != 0:
            print(f"Failed to bind resume to event: {response.json()}")
    except Exception as e:
        print(f"Exception during binding resume: {e}")

def create_feishu_meeting(topic: str, start_time: datetime, candidate_email: str):
    token = get_feishu_tenant_token()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 你的应用的日历ID
    calendar_id = "feishu.cn_WPYG3LHf7kmGwN2Fqpq8dd@group.calendar.feishu.cn"
    url_calendar = f"https://open.feishu.cn/open-apis/calendar/v4/calendars/{calendar_id}/events"
    
    end_time = start_time + timedelta(hours=1)
    
    payload = {
        "summary": topic,
        "description": "TCL FALCON Overseas Product Operation Intern Interview",
        "need_notification": True,
        "attendee_ability": "can_see_others",
        "start_time": {
            "timestamp": str(int(start_time.timestamp())),
            "timezone": "Asia/Shanghai"
        },
        "end_time": {
            "timestamp": str(int(end_time.timestamp())),
            "timezone": "Asia/Shanghai"
        },
        "vchat": {
            "vc_type": "vc"
        }
    }
    
    response = requests.post(url_calendar, headers=headers, json=payload)
    data = response.json()
    
    if data.get("code") != 0:
        print(f"飞书API调用失败: {data}")
        import hashlib
        unique_str = f"{topic}_{int(start_time.timestamp())}"
        hash_obj = hashlib.md5(unique_str.encode('utf-8'))
        room_id = str(int(hash_obj.hexdigest(), 16))[:9]
        return f"https://vc.feishu.cn/j/{room_id}", None
        
    event_id = data.get("data", {}).get("event", {}).get("event_id")
    
    # 关键步骤：把面试官（你）和候选人作为参与人拉进这个日程里
    if event_id:
        url_attendees = f"https://open.feishu.cn/open-apis/calendar/v4/calendars/{calendar_id}/events/{event_id}/attendees?user_id_type=open_id"
        payload_attendees = {
            "attendees": [
                {
                    "type": "user",
                    "is_optional": False,
                    "user_id": FEISHU_USER_ID
                },
                {
                    "type": "third_party",
                    "is_optional": False,
                    "third_party_email": candidate_email
                }
            ]
        }
        # 发送添加参与人请求
        requests.post(url_attendees, headers=headers, json=payload_attendees)
        
    # 从日程返回结果中提取真实会议链接
    vchat_url = data.get("data", {}).get("event", {}).get("vchat", {}).get("meeting_url")
    if not vchat_url:
        import hashlib
        unique_str = f"{topic}_{int(start_time.timestamp())}"
        hash_obj = hashlib.md5(unique_str.encode('utf-8'))
        room_id = str(int(hash_obj.hexdigest(), 16))[:9]
        return f"https://vc.feishu.cn/j/{room_id}", event_id
        
    return vchat_url, event_id

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
async def book_interview(
    response: Response,
    date: str = Form(...),
    time: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    resume: UploadFile = File(None)
):
    try:
        # 解析时间，并且强制指定为系统所在的本地时间，然后生成 timestamp
        dt_str = f"{date} {time}"
        
        # 很多服务器默认是 UTC 时间，我们在 strptime 之后，应该将其视为北京时间(GMT+8)
        # 否则 strptime() 返回的是一个 naive datetime，.timestamp() 会将其当作系统本地时区来转换。
        # 如果系统是 UTC (比如 Vercel)，那么 "21:00" 就会被当作 UTC 的 21:00（即北京时间次日 05:00）！
        import pytz
        tz = pytz.timezone('Asia/Shanghai')
        
        naive_start_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        start_time = tz.localize(naive_start_time)
        
        # 将中文名字转换为拼音，确保飞书 API 在接受时绝对不会因为字符编码报错
        # lazy_pinyin("成都车") -> ['cheng', 'dou', 'che']
        # 然后用空格拼起来，并使用 title() 让首字母大写 -> "Cheng Dou Che"
        pinyin_list = lazy_pinyin(name)
        pinyin_name = " ".join(pinyin_list).title()
        
        topic = f"Interview: {pinyin_name} - Product Ops Intern"
        
        # 1. 创建飞书会议
        event_id = None
        try:
            meeting_url, event_id = create_feishu_meeting(topic, start_time, email)
        except Exception as e:
            # 捕获飞书报错，如果没配好飞书，给个默认链接
            print(f"Warning: {e}")
            meeting_url = "https://vc.feishu.cn/j/mock_link_please_configure_api"
            
        # 2. 处理简历附件上传
        if resume and event_id:
            try:
                # 读取文件内容
                file_content = await resume.read()
                
                # 安全处理文件名
                import urllib.parse
                safe_filename = urllib.parse.quote(resume.filename) if resume.filename else "resume.pdf"
                
                print(f"Uploading resume: {safe_filename}, size: {len(file_content)} bytes")
                file_token = upload_resume_to_feishu(file_content, safe_filename)
                
                if file_token:
                    # 你的应用的日历ID (与创建会议时一致)
                    calendar_id = "feishu.cn_WPYG3LHf7kmGwN2Fqpq8dd@group.calendar.feishu.cn"
                    bind_resume_to_event(calendar_id, event_id, file_token)
                    print("Resume attached to Feishu event successfully.")
            except Exception as e:
                print(f"Error handling resume: {e}")

        # 3. 保存预约记录
        booking_data = {
            "name": name,
            "email": email,
            "date": date,
            "time": time,
            "meeting_url": meeting_url,
            "has_resume": bool(resume),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_booking(email, booking_data)
        
        # 4. 设置 Cookie (有效7天)
        # 注意：cookie的value如果包含非ascii字符（如中文姓名），必须进行URL编码
        # 否则在 set_cookie 内部底层组装 HTTP Headers 时会触发 latin-1 编码错误
        import urllib.parse
        encoded_name = urllib.parse.quote(name)
        
        response.set_cookie(key="interview_email", value=email, max_age=7*24*3600)
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
