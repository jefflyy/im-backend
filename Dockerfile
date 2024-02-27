FROM python:3.9

ENV DEPLOY=1

WORKDIR /app

RUN mkdir -p /app/database/media

COPY requirements.txt /app/

RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY . /app/

EXPOSE 80

CMD ["sh", "start.sh"]