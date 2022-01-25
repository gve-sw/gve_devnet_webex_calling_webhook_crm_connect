FROM python:3.8-slim-buster

MAINTAINER gvedevnet@cisco.com
USER 0
RUN umask 002

RUN apt-get update && apt-get -y install procps libnss-wrapper

RUN mkdir static
RUN mkdir templates

#ADD . .
ADD *.py .
ADD static ./static
ADD templates ./templates
ADD requirements.txt .

ADD requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir

#uncomment/comment the lines below for FLASK_ENV depending on which
#environment you wish to target when building the image
#ENV FLASK_ENV development
ENV FLASK_ENV production

ENV FLASK_APP app.py

#uncomment line below depending if development or production
#ADD .env_local .env
ADD .env_prod .env

EXPOSE 5000

CMD ["python","app.py"]