FROM python:3.9-alpine as builder


RUN mkdir /wheels \
  && python -m pip wheel --wheel-dir /wheels sqlalchemy pyyaml rich ldap3 pymysql dnspython


FROM python:3.9-alpine
LABEL maintainer="alphabet5"

ENV MYSQL_HOSTNAME=mysql
ENV MYSQL_DATABASE=guacamole_db
ENV MYSQL_USER=root
ENV MYSQL_PASSWORD=password
ENV MANUAL_ONLY=false
ENV CFG_AUTO_CONNECTION_DNS=false
ENV CFG_AUTO_CONNECTION_DNS_RESOLVER=192.168.1.1
ENV GUAC_ADMIN_GROUPS='RST-DM-DC01,RDT-DM-DC02'
ENV LDAP_BASE_DN='DC=domain,DC=com'
ENV LDAP_COMPUTER_FILTER='(objectCategory=Computer)'
ENV LDAP_GROUP_NAME_FROM_CONN_NAME_REGEX='(.*?)\..+'
ENV LDAP_GROUP_NAME_MOD='{regex}'
ENV REFRESH_SPEED=300
ENV DEBUG=false

COPY --from=builder /wheels /wheels

RUN python -m pip install --no-cache-dir /wheels/*

COPY guacamole-users.py /guacamole-users.py

CMD [ "python", "/guacamole-users.py" ]
