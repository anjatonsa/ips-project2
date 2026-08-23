FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY model.tflite scaler.pkl ml_service.py .

CMD ["python", "ml_service.py"]

