FROM guacamole/guacamole as sql-script


FROM python:3.9-slim-bullseye
LABEL maintainer="alphabet5"

ENV MYSQL_HOSTNAME=mysql
ENV MYSQL_DB=guacamole_db
ENV MYSQL_USER=root
ENV MYSQL_PASSWORD=password
ENV GUACADMIN_PASSWORD=guacadmin
ENV CFG_AUTO_CONNECTION_DNS=false
ENV CFG_AUTO_CONNECTION_DNS_RESOLVER=192.168.1.1
ENV GUAC_ADMIN_GROUPS='RST-DM-DC01,RDT-DM-DC02'
ENV LDAP_COMPUTER_BASE_DN='DC=domain,DC=com'
ENV LDAP_COMPUTER_FILTER='(objectCategory=Computer)'
ENV LDAP_GROUP_NAME_FROM_CONN_NAME_REGEX='(.*?)\..+'
ENV LDAP_GROUP_NAME_MOD='{regex}'

COPY --from=sql-script /opt/guacamole/mysql/schema/*.sql /templates/sql
COPY templates/* /templates
RUN cat /templates/sql/*.sql > /templates/initdb.sql.script
RUN rm -rf /templates

RUN \
    apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir /templates  \
    && mkdir /templates/sql \
    && mkdir /wheels \
    && python3.9 -m pip wheel --no-cache-dir --wheel-dir /wheels sqlalchemy pyyaml rich ldap3 pymysql dnspython \
    && python3.9 -m pip install --no-cache /wheels/*  \
    && rm -rf /wheels

COPY guacamole-users.py /

CMD [ "python", "./guacamole-users.py" ]
