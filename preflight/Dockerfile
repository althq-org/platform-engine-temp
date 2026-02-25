FROM python:3.12-slim
RUN pip install --no-cache-dir redis psycopg2-binary httpx
COPY verify.py /verify.py
CMD ["python", "/verify.py"]
