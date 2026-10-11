import json
import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./orbit.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase): pass
class Priority(str, Enum): low="low"; medium="medium"; high="high"; urgent="urgent"
class Status(str, Enum): backlog="backlog"; todo="todo"; in_progress="in_progress"; blocked="blocked"; completed="completed"

class User(Base):
    __tablename__="users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, default="Orbit Operator")
    password_hash: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
class SessionToken(Base):
    __tablename__="session_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
class Project(Base):
    __tablename__="projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
class Task(Base):
    __tablename__="tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True)
    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default=Status.todo.value)
    priority: Mapped[str] = mapped_column(String, default=Priority.medium.value)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    estimated_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
class Reminder(Base):
    __tablename__="reminders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    title: Mapped[str] = mapped_column(String)
    remind_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    recurrence: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
class Workflow(Base):
    __tablename__="workflows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
class Activity(Base):
    __tablename__="activity"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String)
    detail: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = ""
    status: Status = Status.todo
    priority: Priority = Priority.medium
    due_at: Optional[datetime] = None
    estimated_minutes: Optional[int] = Field(default=None, ge=1, le=10080)
    project_id: Optional[int] = None
    tags: list[str] = []
class ProjectIn(BaseModel): name:str=Field(min_length=1,max_length=100); description:str=""; deadline:Optional[datetime]=None
class ReminderIn(BaseModel): title:str=Field(min_length=1); remind_at:datetime; task_id:Optional[int]=None; recurrence:Optional[str]=None
class WorkflowIn(BaseModel): name:str=Field(min_length=1); steps:list[str]=[]; active:bool=True
class CommandIn(BaseModel): instruction:str=Field(min_length=3,max_length=2000)
class Plan(BaseModel): summary:str; tasks:list[TaskIn]=[]; reminders:list[ReminderIn]=[]; workflow:Optional[WorkflowIn]=None
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
class LoginIn(BaseModel): email: str; password: str

def db():
    session=SessionLocal()
    try: yield session
    finally: session.close()
def password_hash(password: str, salt: Optional[str] = None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310000).hex()
    return f"{salt}${digest}"
def valid_password(password: str, stored: str):
    if not stored or "$" not in stored: return False
    salt, _ = stored.split("$", 1)
    return secrets.compare_digest(password_hash(password, salt), stored)
def issue_token(session: Session, user: User):
    raw = secrets.token_urlsafe(32)
    session.add(SessionToken(user_id=user.id, token_hash=hashlib.sha256(raw.encode()).hexdigest(), expires_at=datetime.utcnow()+timedelta(days=7)))
    session.commit()
    return raw
def current_user(authorization: Optional[str] = Header(default=None), session: Session=Depends(db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in is required")
    token_hash = hashlib.sha256(authorization[7:].encode()).hexdigest()
    token = session.query(SessionToken).filter_by(token_hash=token_hash).first()
    if not token or token.expires_at < datetime.utcnow(): raise HTTPException(401, "Your session has expired")
    user = session.get(User, token.user_id)
    if not user: raise HTTPException(401, "Account not found")
    return user
def log(session,user,action,detail): session.add(Activity(user_id=user.id,action=action,detail=detail))
def owned(session, model, item_id, user):
    item=session.get(model,item_id)
    if not item or item.user_id!=user.id: raise HTTPException(404,"Resource not found")
    return item
def task_out(task): return {c.name:getattr(task,c.name) for c in Task.__table__.columns}
def seed(session,user):
    if session.query(Task).filter_by(user_id=user.id).first(): return
    project=Project(user_id=user.id,name="TriCity AI Hackathon Submission",description="Demo-ready Orbit AI delivery")
    session.add(project);session.flush()
    samples=[("Finalize project implementation","urgent",1),("Test the AI command pipeline","high",1),("Prepare presentation slides","high",2),("Record the two-minute demo","medium",2),("Upload the project ZIP","urgent",3),("Verify the GitHub repository","medium",3),("Complete the final submission checklist","high",3)]
    for title,priority,days in samples: session.add(Task(user_id=user.id,project_id=project.id,title=title,priority=priority,due_at=datetime.utcnow()+timedelta(days=days)))
    session.add(Reminder(user_id=user.id,title="Demo rehearsal",remind_at=datetime.utcnow()+timedelta(hours=4)))
    session.add(Workflow(user_id=user.id,name="Hackathon submission",steps=["Review scope","Run tests","Package ZIP","Submit" ]))
    log(session,user,"Demo workspace initialized","TriCity hackathon sample data created");session.commit()

app=FastAPI(title="Orbit AI API",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=os.getenv("CORS_ORIGINS","http://localhost:5173,http://127.0.0.1:5173").split(","),allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
@app.on_event("startup")
def start():
    Base.metadata.create_all(engine)
    if DATABASE_URL.startswith("sqlite"):
        with engine.begin() as connection:
            columns = [row[1] for row in connection.exec_driver_sql("PRAGMA table_info(users)")]
            if "password_hash" not in columns: connection.exec_driver_sql("ALTER TABLE users ADD COLUMN password_hash VARCHAR DEFAULT ''")
    scheduler=BackgroundScheduler(); scheduler.start()
@app.get("/health")
def health(): return {"ok":True,"demo_mode":os.getenv("DEMO_MODE","true").lower()=="true"}
@app.post("/auth/register", status_code=201)
def register(data: RegisterIn, session: Session = Depends(db)):
    email = data.email.strip().lower()
    if session.query(User).filter_by(email=email).first(): raise HTTPException(409, "An account already exists for this email")
    user = User(id=secrets.token_urlsafe(18), email=email, name=data.name.strip(), password_hash=password_hash(data.password))
    session.add(user); session.commit(); token = issue_token(session, user)
    return {"token": token, "user": {"name":user.name,"email":user.email}}
@app.post("/auth/login")
def login(data: LoginIn, session: Session = Depends(db)):
    user = session.query(User).filter_by(email=data.email.strip().lower()).first()
    if not user or not valid_password(data.password, user.password_hash): raise HTTPException(401, "Incorrect email or password")
    return {"token":issue_token(session,user),"user":{"name":user.name,"email":user.email}}
@app.get("/auth/me")
def me(user: User = Depends(current_user)): return {"name":user.name,"email":user.email}
@app.post("/demo/reset")
def reset(session:Session=Depends(db), user:User=Depends(current_user)):
    for model in (Task,Project,Reminder,Workflow,Activity): session.query(model).filter_by(user_id=user.id).delete()
    session.commit();seed(session,user);return {"ok":True}
@app.get("/dashboard")
def dashboard(session:Session=Depends(db),user:User=Depends(current_user)):
    seed(session,user); now=datetime.utcnow(); tasks=session.query(Task).filter_by(user_id=user.id).all()
    completed=sum(t.status=="completed" for t in tasks); overdue=sum(t.status!="completed" and t.due_at and t.due_at<now for t in tasks)
    return {"user":user.name,"tasks":len(tasks),"completed":completed,"overdue":overdue,"completion_rate":round(100*completed/max(len(tasks),1)),"priority_distribution":{p:sum(t.priority==p for t in tasks) for p in Priority},"upcoming": [task_out(t) for t in sorted([t for t in tasks if t.due_at and t.status!="completed"],key=lambda x:x.due_at)[:5]],"activity":[{"id":a.id,"action":a.action,"detail":a.detail,"created_at":a.created_at} for a in session.query(Activity).filter_by(user_id=user.id).order_by(Activity.created_at.desc()).limit(6)]}
@app.get("/tasks")
def list_tasks(q:str="",status:Optional[Status]=None,session:Session=Depends(db),user:User=Depends(current_user)):
    query=session.query(Task).filter_by(user_id=user.id)
    if q: query=query.filter(Task.title.ilike(f"%{q}%"))
    if status: query=query.filter_by(status=status.value)
    return [task_out(t) for t in query.order_by(Task.due_at.asc().nullslast(),Task.created_at.desc()).all()]
@app.post("/tasks",status_code=201)
def create_task(data:TaskIn,session:Session=Depends(db),user:User=Depends(current_user)):
    if data.project_id: owned(session,Project,data.project_id,user)
    task=Task(user_id=user.id,**data.model_dump(exclude={"status","priority"}),status=data.status.value,priority=data.priority.value);session.add(task);log(session,user,"Task created",data.title);session.commit();session.refresh(task);return task_out(task)
@app.patch("/tasks/{task_id}")
def update_task(task_id:int,data:TaskIn,session:Session=Depends(db),user:User=Depends(current_user)):
    task=owned(session,Task,task_id,user)
    for key,value in data.model_dump().items(): setattr(task,key,value.value if isinstance(value,Enum) else value)
    log(session,user,"Task updated",task.title);session.commit();return task_out(task)
@app.delete("/tasks/{task_id}",status_code=204)
def delete_task(task_id:int,session:Session=Depends(db),user:User=Depends(current_user)):
    task=owned(session,Task,task_id,user);session.delete(task);log(session,user,"Task deleted",task.title);session.commit()
@app.get("/projects")
def projects(session:Session=Depends(db),user:User=Depends(current_user)):
    result=[]
    for p in session.query(Project).filter_by(user_id=user.id):
        ts=session.query(Task).filter_by(user_id=user.id,project_id=p.id).all();result.append({"id":p.id,"name":p.name,"description":p.description,"deadline":p.deadline,"progress":round(100*sum(t.status=="completed" for t in ts)/max(len(ts),1)),"task_count":len(ts)})
    return result
@app.post("/projects")
def create_project(data:ProjectIn,session:Session=Depends(db),user:User=Depends(current_user)):
    item=Project(user_id=user.id,**data.model_dump());session.add(item);log(session,user,"Project created",item.name);session.commit();return {"id":item.id,"name":item.name}
@app.get("/reminders")
def reminders(session:Session=Depends(db),user:User=Depends(current_user)):
    return [{c.name:getattr(r,c.name) for c in Reminder.__table__.columns} for r in session.query(Reminder).filter_by(user_id=user.id,dismissed=False).order_by(Reminder.remind_at).all()]
@app.post("/reminders")
def create_reminder(data:ReminderIn,session:Session=Depends(db),user:User=Depends(current_user)):
    r=Reminder(user_id=user.id,**data.model_dump());session.add(r);log(session,user,"Reminder created",r.title);session.commit();return {"id":r.id}
@app.get("/workflows")
def workflows(session:Session=Depends(db),user:User=Depends(current_user)): return [{"id":w.id,"name":w.name,"steps":w.steps,"active":w.active} for w in session.query(Workflow).filter_by(user_id=user.id)]
@app.post("/workflows")
def create_workflow(data:WorkflowIn,session:Session=Depends(db),user:User=Depends(current_user)):
    w=Workflow(user_id=user.id,**data.model_dump());session.add(w);log(session,user,"Workflow created",w.name);session.commit();return {"id":w.id}
@app.post("/workflows/{workflow_id}/run")
def run_workflow(workflow_id:int,session:Session=Depends(db),user:User=Depends(current_user)):
    w=owned(session,Workflow,workflow_id,user);log(session,user,"Workflow executed",f"{w.name}: {len(w.steps)} steps completed");session.commit();return {"message":"Workflow execution recorded","steps_completed":len(w.steps)}
def fallback_plan(instruction:str):
    lower=instruction.lower(); priority=Priority.urgent if "urgent" in lower or "high" in lower else Priority.medium
    due=datetime.utcnow()+timedelta(days=1 if "tomorrow" in lower else 3)
    title=instruction.strip().rstrip(".")[:120]
    return Plan(summary="Orbit generated a safe draft for your review.",tasks=[TaskIn(title=title,priority=priority,due_at=due)])
@app.post("/ai/plan")
def ai_plan(data:CommandIn):
    if not os.getenv("OPENAI_API_KEY"): return {"plan":fallback_plan(data.instruction),"source":"fallback","notice":"AI key is not configured; this editable local draft was generated instead."}
    try:
        client=OpenAI(timeout=15); response=client.responses.parse(model="gpt-4o-mini",input=f"Convert this into a concise operations plan: {data.instruction}",text_format=Plan);return {"plan":response.output_parsed,"source":"openai"}
    except Exception: return {"plan":fallback_plan(data.instruction),"source":"fallback","notice":"AI service was unavailable; review this draft before applying."}
@app.post("/ai/approve")
def approve(plan:Plan,session:Session=Depends(db),user:User=Depends(current_user)):
    created=[]
    for data in plan.tasks:
        task=Task(user_id=user.id,**data.model_dump(exclude={"status","priority"}),status=data.status.value,priority=data.priority.value);session.add(task);created.append(data.title)
    for data in plan.reminders: session.add(Reminder(user_id=user.id,**data.model_dump()))
    if plan.workflow: session.add(Workflow(user_id=user.id,**plan.workflow.model_dump()))
    log(session,user,"AI plan approved",f"Created {len(created)} tasks");session.commit();return {"created":created}
@app.get("/analytics")
def analytics(session:Session=Depends(db),user:User=Depends(current_user)):
    tasks=session.query(Task).filter_by(user_id=user.id).all();return {"by_status":{s:sum(t.status==s for t in tasks) for s in Status},"by_priority":{p:sum(t.priority==p for t in tasks) for p in Priority}}
@app.get("/activity")
def activity(session:Session=Depends(db),user:User=Depends(current_user)): return [{"action":a.action,"detail":a.detail,"created_at":a.created_at} for a in session.query(Activity).filter_by(user_id=user.id).order_by(Activity.created_at.desc()).limit(50)]

frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.isdir(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        asset = os.path.join(frontend_dist, path)
        if path and os.path.isfile(asset): return FileResponse(asset)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
