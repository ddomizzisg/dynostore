FROM python:3.12


ADD requirements.txt /install/requirements.txt
WORKDIR /install

RUN pip install -r requirements.txt --no-cache-dir
RUN pip install git+https://github.com/CoCo-ARCOS/kagio-client.git

ADD start.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ADD app /app
WORKDIR /app


EXPOSE 80


CMD ["hypercorn", "main:app", "--bind", "0.0.0.0:80"]
