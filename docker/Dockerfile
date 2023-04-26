FROM python:3.10

ENV PYTHONUNBUFFERED=1

RUN apt-get update -y
RUN python -m pip install --upgrade pip

COPY /cremaet_bot /cremaet_bot
WORKDIR /cremaet_bot
RUN chmod +x entrypoint.sh

RUN pip install -r requirements.txt

# There is no need for expose, this app does not have an API
# CMD ["python", "main.py"]
