import os
os.environ["DATABASE_URL"]="sqlite:///./test_orbit.db"
from fastapi.testclient import TestClient
from backend.main import app, Base, engine

Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
client=TestClient(app)

def headers():
    response = client.post('/auth/register', json={'name':'Test User','email':'test@example.com','password':'SecurePass123'})
    if response.status_code == 409:
        response = client.post('/auth/login', json={'email':'test@example.com','password':'SecurePass123'})
    return {'Authorization': f"Bearer {response.json()['token']}"}

def test_task_lifecycle_and_dashboard():
    auth=headers(); created=client.post('/tasks',headers=auth,json={'title':'Validate persistence','priority':'high'}); assert created.status_code==201
    task=created.json(); updated=client.patch(f"/tasks/{task['id']}",headers=auth,json={'title':'Validate persistence','priority':'high','status':'completed','tags':[]}); assert updated.status_code==200
    assert client.get('/dashboard',headers=auth).json()['completed'] >= 1

def test_ai_plan_and_approval():
    auth=headers(); plan=client.post('/ai/plan',json={'instruction':'Create a high priority demo task tomorrow'}); assert plan.status_code==200
    payload=plan.json()['plan']; assert payload['tasks']
    assert client.post('/ai/approve',headers=auth,json=payload).status_code==200

def test_missing_resource_is_not_exposed():
    assert client.delete('/tasks/999999',headers=headers()).status_code==404
