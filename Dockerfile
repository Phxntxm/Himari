FROM python:3.11

WORKDIR /app

RUN apt-get update 
RUN apt-get install ca-certificates

RUN pip install --upgrade pip
RUN pip install pipenv

COPY Pipfile Pipfile.lock /app/
RUN pipenv install --system --deploy

COPY config.py /app/
COPY main.py /app/

COPY src /app/src

CMD ["python", "-u", "main.py"]
