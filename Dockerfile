FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend ./backend
COPY --from=frontend /app/frontend/dist ./frontend/dist
RUN mkdir -p /var/data
WORKDIR /app/backend
ENV DATABASE_URL=sqlite:////var/data/orbit.db
ENV PORT=10000
EXPOSE 10000
CMD sh -c "uvicorn main:app --host 0.0.0.0 --port ${PORT}"
