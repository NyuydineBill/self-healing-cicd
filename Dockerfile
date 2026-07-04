FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install -r requirements-validation.txt

CMD ["pytest"]
