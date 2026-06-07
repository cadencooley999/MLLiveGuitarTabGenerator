# 1. Base Python image
FROM python:3.11-slim

# 2. Set working directory inside container
WORKDIR /app

# 3. Copy dependency file first (for caching)
COPY requirements.txt .

# 4. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy ALL your backend code
COPY . .

# 6. Cloud Run uses this port
ENV PORT=8080

# 7. Start FastAPI with uvicorn
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]