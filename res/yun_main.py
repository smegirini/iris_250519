import traceback
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import fn1
import asyncio
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import logging
from time import sleep
import os
from pathlib import Path
import ctypes

# ==================================================
my_room = '수홍'
# ==================================================

# 로깅 설정
logging.basicConfig(
    filename='kakaotalk.log',
    level=logging.INFO,  # DEBUG에서 INFO로 변경
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 실행
    # 백그라운드 태스크 없음
    try:
        yield
    finally:
        # 종료 시 실행 (현재 취소할 백그라운드 태스크 없음)
        pass

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
    <head></head>
    <body>
        <center><h1>안돼, 돌아가</h1></center>
    </body>
    </html>
    """

@app.get("/man", response_class=HTMLResponse)
async def workforce(request: Request):
    try:
        # 현장인력 데이터 조회
        query = """
        SELECT id, name, birthdate, experience, is_team_leader, available, phone_number
        FROM workforce
        ORDER BY id
        """
        workers = fn1.fetch_all(query)
        
        # 데이터 가공
        formatted_workers = []
        total_experience = 0
        team_leader_count = 0
        available_count = 0
        
        for worker in workers:
            worker_dict = {
                'id': worker[0],
                'name': worker[1],
                'birthdate': worker[2],
                'experience': worker[3],
                'is_team_leader': worker[4],
                'available': worker[5],
                'phone_number': worker[6]
            }
            
            formatted_workers.append(worker_dict)
            total_experience += worker[3]
            
            if worker[4] == 1:  # is_team_leader
                team_leader_count += 1
                
            if worker[5] == 1:  # available
                available_count += 1
        
        # 통계 계산
        total_count = len(workers)
        avg_experience = round(total_experience / total_count, 1) if total_count > 0 else 0
        
        return templates.TemplateResponse(
            "workforce.html",
            {
                "request": request,
                "workers": formatted_workers,
                "total_count": total_count,
                "team_leader_count": team_leader_count,
                "available_count": available_count,
                "avg_experience": avg_experience
            }
        )
    except Exception as e:
        logger.error(f"Error in workforce endpoint: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_message": f"현장인력 정보를 불러오는 중 오류가 발생했습니다: {str(e)}"
            }
        )

@app.post("/api/kakaotalk")
async def kakaotalk(request: Request):
    try:
        data = await request.json()
        room = data.get('room', '')
        msg = data.get('msg', '')
        sender = data.get('sender', '')
        is_group_chat = data.get('is_group_chat', False)
        is_mention = data.get('is_mention', False)
        log_id = data.get('log_id')
        channel_id = data.get('channel_id')
        user_hash = data.get('user_hash')
        
        # 메시지 처리
        reply_msg = fn1.get_reply_msg(room, sender, msg, is_group_chat, is_mention, log_id, channel_id, user_hash)
        
        if reply_msg:
            result = {
                'is_reply': True, 
                'reply_room': room, 
                'reply_msg': reply_msg
            }
            
            fn1.log(result)
            return result
        
        return {'is_reply': False}
        
    except Exception as e:
        logger.error(f"Error in kakaotalk endpoint: {str(e)}")
        return {'is_reply': False, 'error': str(e)}

@app.get("/weekly-plans", response_class=HTMLResponse)
async def weekly_plans(request: Request, week_offset: int = 0, month_offset: int = 0):
    today = datetime.now().date()
    # 현재 주의 월요일과 일요일 계산 (월요일: weekday()=0)
    current_monday = today - timedelta(days=today.weekday())
    
    # week_offset에 따라 주 이동
    monday = current_monday + timedelta(weeks=week_offset)
    sunday = monday + timedelta(days=6)
    
    # 주간 일정 데이터 조회
    query = "SELECT schedule_date, sender, content FROM schedule WHERE schedule_date BETWEEN %s AND %s ORDER BY schedule_date, sender"
    rows = fn1.fetch_all(query, (monday, sunday))
    
    # 날짜별 일정 그룹화
    schedule_by_date = {}
    for row in rows:
        date, sender, content = row
        schedule_by_date.setdefault(date, []).append({"sender": sender, "content": content})
    
    # 템플릿에 전달할 데이터 준비
    days = []
    for i in range(7):
        day = monday + timedelta(days=i)
        days.append({
            "date": day,
            "schedules": schedule_by_date.get(day, [])
        })
        
    # 월간 달력 데이터 준비
    # 현재 월의 1일 계산
    current_month_first_day = today.replace(day=1)
    
    # month_offset에 따라 월 이동
    target_month = current_month_first_day
    if month_offset > 0:
        for _ in range(month_offset):
            # 다음 달 1일 계산
            if target_month.month == 12:
                target_month = target_month.replace(year=target_month.year + 1, month=1)
            else:
                target_month = target_month.replace(month=target_month.month + 1)
    elif month_offset < 0:
        for _ in range(abs(month_offset)):
            # 이전 달 1일 계산
            if target_month.month == 1:
                target_month = target_month.replace(year=target_month.year - 1, month=12)
            else:
                target_month = target_month.replace(month=target_month.month - 1)
    
    month_start = target_month
    
    # 선택된 월의 마지막 날짜 계산
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)
    month_end = next_month - timedelta(days=1)
    
    # 월간 일정 데이터 조회
    month_query = "SELECT schedule_date, sender, content FROM schedule WHERE schedule_date BETWEEN %s AND %s ORDER BY schedule_date, sender"
    month_rows = fn1.fetch_all(month_query, (month_start, month_end))
    
    # 날짜별 일정 그룹화
    month_schedule_by_date = {}
    for row in month_rows:
        date, sender, content = row
        month_schedule_by_date.setdefault(date, []).append({"sender": sender, "content": content})
    
    # 월간 달력 만들기 - 1일이 시작하는 요일부터 마지막 날까지
    # 시작 날짜는 해당 월 1일이 속한 주의 월요일
    start_weekday = month_start.weekday()  # 1일의 요일 (0:월요일, 6:일요일)
    calendar_start = month_start - timedelta(days=start_weekday)
    
    # 종료 날짜는 해당 월 마지막 일이 속한 주의 일요일
    end_weekday = month_end.weekday()
    calendar_end = month_end + timedelta(days=(6 - end_weekday))
    
    # 월간 달력 데이터 구성 (6주 기준)
    month_calendar = []
    current_date = calendar_start
    
    while current_date <= calendar_end:
        week = []
        for _ in range(7):  # 월~일 (7일)
            day_data = {
                "date": current_date,
                "events": month_schedule_by_date.get(current_date, []),
                "other_month": current_date.month != month_start.month
            }
            week.append(day_data)
            current_date += timedelta(days=1)
        month_calendar.append(week)
    
    return templates.TemplateResponse(
        "weekly_plans.html",
        {
            "request": request,
            "monday": monday,
            "sunday": sunday,
            "days": days,
            "today": today,
            "week_offset": week_offset,
            "month_offset": month_offset,
            "month_start": month_start,
            "month_end": month_end,
            "month_calendar": month_calendar
        }
    )

def prevent_sleep():
    """Windows 시스템의 절전 모드 진입을 방지"""
    try:
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        logger.info("절전 모드 방지 설정 완료")
    except Exception as e:
        logger.error(f"절전 모드 방지 설정 실패: {str(e)}")

if __name__ == "__main__":
    prevent_sleep()  # 프로그램 시작 시 절전 모드 방지
    uvicorn.run(app, host="0.0.0.0", port=8011)
