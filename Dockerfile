FROM python:3.12-slim
WORKDIR /project
COPY requirements*.txt ./
RUN python -m pip install --no-cache-dir -r requirements-dev.txt
COPY . .
CMD ["sh", "scripts/check.sh"]
