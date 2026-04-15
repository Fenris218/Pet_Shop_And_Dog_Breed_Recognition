FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Cài dependencies hệ thống (bắt buộc cho mysqlclient + build package)
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# copy requirements trước để cache build
COPY requirements.txt .

RUN pip install --upgrade pip && pip install -r requirements.txt

# copy toàn bộ source code
COPY . .

# collect static (an toàn, không crash nếu chưa config)
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

# chạy production server
CMD ["gunicorn", "catdog_project.wsgi:application", "--bind", "0.0.0.0:8000"]