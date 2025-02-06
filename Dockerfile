FROM python:3.10

RUN apt-get update && apt-get install -y fluidsynth

WORKDIR /app

COPY app/ ./app/
COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

ENV PORT 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
