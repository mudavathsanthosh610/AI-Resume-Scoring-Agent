FROM python:3.11-slim

# Set working directory to the app folder
WORKDIR /app

# Copy only necessary files first for better caching
COPY requirements.txt ./
RUN python -m pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

# Expose port used by uvicorn
EXPOSE 8000

# Use uvicorn to serve the FastAPI app
# Shell form for $PORT expansion (Railway injects PORT at runtime)
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
