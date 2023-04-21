FROM python:3.10

ENV PYTHONUNBUFFERED=1

RUN apt-get update -y
RUN python -m pip install --upgrade pip

COPY /wakamola_telegram_front /wakamola_telegram_front
WORKDIR /wakamola_telegram_front
RUN chmod +x entrypoint.sh

RUN pip install -r requirements.txt

# There is no need for expose, this app does not have an API
# CMD ["python", "main.py"]