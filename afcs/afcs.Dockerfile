FROM cr.yandex/mirror/ubuntu:22.04

ENV DEBIAN_FRONTEND noninteractive
ENV FLASK_APP afcs_server.py
RUN printf "deb http://mirror.yandex.ru/ubuntu jammy main universe multiverse \ndeb http://mirror.yandex.ru/ubuntu jammy-security main universe multiverse \ndeb http://mirror.yandex.ru/ubuntu jammy-backports main universe multiverse \ndeb-src http://mirror.yandex.ru/ubuntu jammy main" > /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y \
        apache2 \
        libapache2-mod-wsgi-py3 \
        net-tools \
        mosquitto \
        python3 \
        python3-pip \
        python3-venv \
        python3-blinker \
        python3-flask \
        python3-flask-migrate \
        python3-flask-sqlalchemy \
        python3-greenlet \
        python3-itsdangerous \
        python3-mako \
        python3-markupsafe \
        python3-pycryptodome \
        python3-typing-extensions \
        python3-werkzeug \
        python3-jinja2 \
        python3-pytest \
        python3-flasgger \
        python3-paho-mqtt && \
    apt-get clean && \
    mkdir -p /var/www/afcs 

COPY ./afcs/default.conf /etc/mosquitto/conf.d/default.conf
COPY ./afcs /var/www/afcs
COPY ./afcs.conf.docker /etc/apache2/sites-available/afcs.conf

RUN cd /var/www/afcs \
    && a2ensite afcs.conf \
    && rm /etc/apache2/sites-available/000-default.conf \
    && echo export ADMIN_LOGIN=admin >> /etc/apache2/envvars \
    && echo export ADMIN_PASSW=passw >> /etc/apache2/envvars \
    && sed -i -e 's/ErrorLog.*$/ErrorLog \/dev\/stderr/g' /etc/apache2/apache2.conf \
    && echo "Listen 8080" >> /etc/apache2/ports.conf \
    && chmod -R 777 /var/www/afcs \
    && chmod +x /var/www/afcs/start.sh

CMD ["/var/www/afcs/start.sh"]
